"""compaction-v5 clean-return (cv5-CR, 50% swap) served by SGLang instead of vLLM: 5 x 96k or 7 x 66k lanes.

Son, 25-Sep: "do compaction-v5 50% swap on 5 x 96k and 7 x 66k for me. Vary the time limit per game accordingly."
The SGLang line (fork gabrielolympie/sglang-flashnext-sm120 on official qwen4-main-squashed; MTP NEXTN k=3 lossless,
fp8 KV, fp8 weight copies, hierarchical host cache) measured 440-755 tok/s aggregate at the harness shape against ~290
on every vLLM scored run. Its GPU pool is 520k tokens at mem-fraction 0.95, so LANES x CTX must fit: 5 x 98,304 = 492k,
7 x 67,584 = 473k. Games in flight = lanes (the runner's lane model is unchanged; parking is the next step).

Base: compaction_v5_clean_return_a (19-Sep, 14.56 on all 25 at 132 min). Everything not listed is byte-identical.
Moves, as in lacr-mtp64k/derive_c60k_mtp.py: every 102985 / 94281 / 7-lane / 2061-s pin in runner, runtime_probe,
CONFIG_FLAGS (+config_id), candidate FEATURE_ARM.json, release manifest, selftest bundle, ADAPTER, startup.
New in startup: the vLLM container, its PLE/QSA/scheduler/retention overlays and the vLLM capacity gate, prefix reset
and metrics sampler are replaced by (1) an SGLang build (docker CUDA 13 dev image + fork patches, committed as
arc3-sglang:built), (2) a serve wrapper whose argv keeps the vLLM flag names the runtime probe reads from docker
inspect (--gpu-memory-utilization/--kv-cache-dtype/--max-model-len/--max-num-seqs), (3) a vLLM-compat shim on :1234
in front of SGLang on :1235 (/tokenize with messages+tools+images via a 1-token completion, max_model_len on /v1/models,
preserve_thinking default), (4) a serving gate that asserts /tokenize == usage.prompt_tokens on text, image and the
selftest fixture, LANES concurrent long prefixes, a vision request and a parsed tool call.

usage: ARC3_CTX=98304 ARC3_LANES=5 python derive_sgl.py   |   ARC3_CTX=67584 ARC3_LANES=7 python derive_sgl.py
"""
import hashlib, io, json, os, re, shutil, sys, tarfile, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC_KIND = os.environ.get("ARC3_SRC", "cv5cr")   # cv5cr = compaction v5 + clean return (50% swap + ledger); cr = clean return (50% swap, no ledger)
SRC = {"cv5cr": Path(r"D:\codex-work\compaction-v5-clean-return132-20260919\arms\compaction_v5_clean_return_a"),
       "cr": Path(r"D:\codex-work\clean-return-repeat132-r5-20260917\arms\clean_return_repeat132")}[SRC_KIND]
PARENT_RUN = {"cv5cr": "g4run-compaction-v5-clean-return-a132-w7-20260919-693e7fd43c", "cr": "g4run-clean-return-repeat132-w7-20260917-9677f73fbf"}[SRC_KIND]
SWAP = os.environ.get("ARC3_SWAP", "1") == "1"        # ARC3_SWAP=0: no 50% half-context swap either -> plain oldest-turn trimming at the budget
SLOTS = int(os.environ.get("ARC3_SLOTS", os.environ.get("ARC3_LANES", "5")))   # server decode slots; LANES > SLOTS = games parked in the host cache
BUCKET_CODE = "gs://cellens-ai-artifacts/arc3-duck/code/sglang-cv5cr-v1"
RUNNER_DIR = BUCKET_CODE
CTX, OLD_CTX = int(os.environ.get("ARC3_CTX", "98304")), 102985
LANES = int(os.environ.get("ARC3_LANES", "5")); OLD_LANES = 7
WAVES = -(-25 // LANES)                          # ceil(25 / lanes): 5 lanes -> 5 waves, 6 -> 5, 7 -> 4
GAME_S, OLD_GAME_S = (7920 // WAVES if LANES != 7 else 2061), 2061   # 132 min / waves; 7 lanes keep the source pin (4 waves x 2061)
MEMFRAC = os.environ.get("ARC3_MEMFRAC", "0.95")   # 0.98 OOMs in graph capture, 0.965 OOMs on the first request with the fp8 copies
HICACHE_GB = int(os.environ.get("ARC3_HICACHE_GB", "64"))
assert SLOTS * CTX <= 520_000, (SLOTS, CTX, "does not fit the 520k-token GPU pool at mem 0.95")
assert SLOTS <= LANES
BUDGET, OLD_BUDGET = CTX - 8192 - 512, 94281
assert OLD_BUDGET == OLD_CTX - 8192 - 512
ARM_NAME = f"{SRC_KIND}_sgl_c{CTX//1024}k_w{LANES}" + (f"_s{SLOTS}" if SLOTS != LANES else "") + ("" if LANES in (5, 7) else f"_g{GAME_S}") + ("" if SWAP else "_noswap")
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
def litn(old, new, text, expected):
    assert text.count(old) == expected, (old[:80], text.count(old), expected)
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
work = HERE / "_work"
if work.exists(): shutil.rmtree(work)
work.mkdir()

# ---------------------------------------------------------------- candidate bundle: FEATURE_ARM.json
cand_dir = work / "candidate"; cand_dir.mkdir()
with tarfile.open(SRC / "candidate.tgz") as t:
    cand_names = t.getnames(); t.extractall(cand_dir)
fa = json.loads((cand_dir / "FEATURE_ARM.json").read_text(encoding="utf-8"))
assert fa["context_window"] == OLD_CTX and fa["environment"]["LOCAL_ANALYZER_CONTEXT_WINDOW"] == str(OLD_CTX)
fa["context_window"] = CTX; fa["environment"]["LOCAL_ANALYZER_CONTEXT_WINDOW"] = str(CTX)
if LANES != OLD_LANES:
    assert fa["game_seconds"] == OLD_GAME_S and fa["environment"]["ARC3_MAX_RUNTIME_S_PER_GAME"] == str(OLD_GAME_S)
    fa["game_seconds"] = GAME_S; fa["environment"]["ARC3_MAX_RUNTIME_S_PER_GAME"] = str(GAME_S)
    if fa["environment"].get("ARC3_BENCHMARK_CONCURRENCY") == str(OLD_LANES): fa["environment"]["ARC3_BENCHMARK_CONCURRENCY"] = str(LANES)
    for k in ("lanes", "concurrency", "workers"):
        if fa.get(k) == OLD_LANES: fa[k] = LANES
fa_bytes = (json.dumps(fa, indent=2) + NL).encode()
(cand_dir / "FEATURE_ARM.json").write_bytes(fa_bytes)
candidate_bytes = repack(cand_dir, cand_names); (ARM / "candidate.tgz").write_bytes(candidate_bytes)
candidate_sha = sha_b(candidate_bytes); old_candidate_sha = sha_b((SRC / "candidate.tgz").read_bytes())

# ---------------------------------------------------------------- selftest bundle + release manifest
st_dir = work / "selftest"; st_dir.mkdir()
with tarfile.open(SRC / "selftest.tgz") as t:
    st_names = t.getnames(); t.extractall(st_dir)
fc = st_dir / "feature_contract.py"; x = fc.read_text(encoding="utf-8")
x = sub1(rf"^CONTEXT = {OLD_CTX}$", f"CONTEXT = {CTX}", x, re.M)
if LANES != OLD_LANES:
    x = sub1(r"^LANES = 7$", f"LANES = {LANES}", x, re.M); x = sub1(rf"^GAME_SECONDS = {OLD_GAME_S}$", f"GAME_SECONDS = {GAME_S}", x, re.M)
fc.write_text(x, encoding="utf-8", newline=NL)
hg = st_dir / "live_half_swap_gate.py"; x = hg.read_text(encoding="utf-8")
x = sub1(rf"production=={OLD_BUDGET}", f"production=={BUDGET}", x); hg.write_text(x, encoding="utf-8", newline=NL)
(st_dir / "candidate" / "FEATURE_ARM.json").write_bytes(fa_bytes)
man = json.loads((st_dir / "release-manifest.json").read_text(encoding="utf-8"))
man["candidate_files"]["FEATURE_ARM.json"] = sha_b(fa_bytes)
man["candidate_bundle_sha256"] = candidate_sha
man["source_tree_sha256"] = sha_b(enc(man["candidate_files"]))
assert str(OLD_CTX) in json.dumps(man)
def fix_ctx(obj):
    if isinstance(obj, dict): return {k: fix_ctx(v) for k, v in obj.items()}
    if isinstance(obj, list): return [fix_ctx(v) for v in obj]
    if obj == OLD_CTX: return CTX
    if obj == str(OLD_CTX): return str(CTX)
    return obj
man = fix_ctx(man)
if LANES != OLD_LANES:
    def fix_clock(obj):
        if isinstance(obj, dict): return {k: fix_clock(v) for k, v in obj.items()}
        if isinstance(obj, list): return [fix_clock(v) for v in obj]
        if obj == OLD_GAME_S: return GAME_S
        if obj == str(OLD_GAME_S): return str(GAME_S)
        return obj
    man = fix_clock(man); assert str(OLD_GAME_S) not in json.dumps(man)
    assert man["environment"]["ARC3_BENCHMARK_CONCURRENCY"] == str(OLD_LANES)
    def fix_lanes(obj):
        if isinstance(obj, dict): return {k: (str(LANES) if k == "ARC3_BENCHMARK_CONCURRENCY" and v == str(OLD_LANES) else fix_lanes(v)) for k, v in obj.items()}
        if isinstance(obj, list): return [fix_lanes(v) for v in obj]
        return obj
    man = fix_lanes(man)
# (the manifest's half_context_swap block describes the shipped module, not its on/off env; the switch lives in CONFIG_FLAGS + startup)
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
r = sub1(rf"full_context{OLD_CTX}", f"full_context{CTX} SGLANG", r)
if LANES != OLD_LANES:
    r = sub1(rf"assert bm\.solver\.max_runtime_s_per_game == {OLD_GAME_S}\.0", f"assert bm.solver.max_runtime_s_per_game == {GAME_S}.0", r)
    r = sub1(r"assert bm\.solver\.concurrency == 7", f"assert bm.solver.concurrency == {LANES}", r)
    r = sub1(rf"7 workers, {OLD_GAME_S} seconds/game, ", f"{LANES} workers, {GAME_S} seconds/game, ", r)
    r = sub1(rf"# 4 waves at {OLD_GAME_S} seconds/game fit the 132-minute suite", f"# {25 // LANES + (25 % LANES > 0)} waves at {GAME_S} seconds/game fit the 132-minute suite", r)
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
p = sub1(r"'--gpu-memory-utilization'\)\+1\]=='0\.965'", f"'--gpu-memory-utilization')+1]=='{MEMFRAC}'", p)
if LANES != OLD_LANES:
    p = sub1(r"'--max-num-seqs'\)\+1\]=='7'", f"'--max-num-seqs')+1]=='{SLOTS}'", p)
elif SLOTS != LANES:
    p = sub1(r"'--max-num-seqs'\)\+1\]=='7'", f"'--max-num-seqs')+1]=='{SLOTS}'", p)
if not SWAP:
    p = lit1("    assert os.environ.get(rc.FLAG) == cfg['recipe']['extra_environment'][rc.FLAG] == '1'\n    assert agent._half_swap is not None and rc.VERSION == 'half_context_swap_v1'\n",
             "    assert os.environ.get(rc.FLAG) == cfg['recipe']['extra_environment'][rc.FLAG] == '0'   # no half-context swap in this arm\n    assert agent._half_swap is None\n", p)
    p = lit1("    gate=json.loads(Path('/opt/arc3/half-swap-live-gate.json').read_text())\n    assert gate['status']=='passed' and gate['no_generation_verified']\n    assert gate['generation_calls']==0 and gate['retained_tail_byte_equal']\n    assert gate['module_sha256']==sha(Path(rc.__file__).read_bytes())\n    assert gate['input_budget']==agent._context_budget_tokens==" + str(BUDGET) + "\n",
             "    gate=json.loads(Path('/opt/arc3/half-swap-live-gate.json').read_text())\n    assert gate['status']=='skipped' and gate['half_swap']=='off'\n    assert agent._context_budget_tokens==" + str(BUDGET) + "\n", p)
assert str(OLD_CTX) not in p and str(OLD_BUDGET) not in p
(ARM / "runtime_probe.py").write_text(p, encoding="utf-8", newline=NL)
probe_sha = sha_b((ARM / "runtime_probe.py").read_bytes()); old_probe_sha = sha_b((SRC / "runtime_probe.py").read_bytes())

# ---------------------------------------------------------------- CONFIG_FLAGS.json
cfg = json.loads((SRC / "CONFIG_FLAGS.json").read_text(encoding="utf-8-sig")); rec = cfg["recipe"]
assert rec["extra_environment"]["LOCAL_ANALYZER_CONTEXT_WINDOW"] == str(OLD_CTX)
assert rec["limits"]["context_tokens"] == OLD_CTX and rec["limits"]["input_tokens"] == OLD_BUDGET
rec["extra_environment"]["LOCAL_ANALYZER_CONTEXT_WINDOW"] = str(CTX)
rec["extra_environment"]["ARC3_SERVING_SPECULATIVE"] = f"sglang-nextn3-c{CTX}-w{LANES}-s{SLOTS}"
if not SWAP:
    assert rec["extra_environment"]["ARC3_HALF_CONTEXT_SWAP"] == "1"; rec["extra_environment"]["ARC3_HALF_CONTEXT_SWAP"] = "0"
rec["limits"]["context_tokens"] = CTX; rec["limits"]["input_tokens"] = BUDGET
if LANES != OLD_LANES:
    assert rec["limits"]["lanes"] == OLD_LANES and rec["limits"]["game_seconds"] == OLD_GAME_S
    rec["limits"]["lanes"] = LANES; rec["limits"]["game_seconds"] = GAME_S
    rec["extra_environment"]["ARC3_BENCHMARK_CONCURRENCY"] = str(LANES); rec["extra_environment"]["ARC3_MAX_RUNTIME_S_PER_GAME"] = str(GAME_S)
rec["source_sha256"] = source_sha256
cfg["run_id"] = f"g4run-{SRC_KIND}-sgl-c{CTX//1024}k-a132-w{LANES}" + (f"s{SLOTS}" if SLOTS != LANES else "") + ("" if SWAP else "-noswap") + "-20260925"
cfg["evidence"]["notes"] = [
    "September25 user: 'do compaction-v5 50% swap on 5 x 96k and 7 x 66k for me. Vary the time limit per game accordingly.' "
    f"cv5-CR (compaction_v5_clean_return_a) served by SGLang (fork sglang-flashnext-sm120 on qwen4-main-squashed; NEXTN MTP k=3 "
    f"lossless, fp8 KV, fp8 weight copies, {HICACHE_GB} GB hierarchical host cache, mem-fraction {MEMFRAC}) with {LANES} lanes x {CTX} context "
    f"({LANES * CTX} of the 520k-token GPU pool), input budget {BUDGET}, {GAME_S} s per game, 132 minutes, Spot. A vLLM-compat shim on "
    ":1234 provides /tokenize and max_model_len; a serving gate asserts tokenize == usage on text, image and the selftest fixture. "
    "SGLang measured 440-755 tok/s aggregate at the harness shape vs ~290 on every vLLM scored run. Prompts, tools, cap 14/return, "
    "time-only guidance, 50% swap: unchanged.",
] + cfg["evidence"]["notes"][1:]
cfg["config_id"] = contract.config_id(rec); contract.validate(cfg, for_launch=True)
cfg_bytes = (json.dumps(cfg, indent=2) + NL).encode(); (ARM / "CONFIG_FLAGS.json").write_bytes(cfg_bytes)
cfg_sha = sha_b(cfg_bytes); old_cfg_sha = sha_b((SRC / "CONFIG_FLAGS.json").read_bytes())

# ---------------------------------------------------------------- startup.sh
s = (SRC / "startup.sh").read_text(encoding="utf-8")
head = s.splitlines()[1]
s = s.replace(head, f"# cv5-CR on SGLang, {LANES} x {CTX} context, {GAME_S} s/game: {head.lstrip('# ')}", 1)

# ---- (1) vLLM container + overlays -> SGLang build; keep the model-mirror attestation and model-info ----
cut_a = s.index("CONVERTER_OBJECT=$(meta arc3-converter-object)")
cut_b = s.index("start_server() {")
sgl_build = r'''# ---- SGLang serving stack: official sglang qwen4-main-squashed + gabrielolympie/sglang-flashnext-sm120 patches ----
# Built once inside a CUDA 13 dev container and committed as arc3-sglang:built; the serve container reuses that image.
SGL_IMAGE_BASE='nvidia/cuda:13.0.3-devel-ubuntu24.04'
SGL_IMAGE='arc3-sglang:built'
mkdir -p /opt/arc3/sgl/cache
cd /opt/arc3/sgl
git clone -q -b qwen4-main-squashed https://github.com/sgl-project/sglang sglang-official
git clone -q https://github.com/gabrielolympie/sglang-flashnext-sm120 fork
(cd sglang-official && git log -1 --format='%H %cd %s') | tee /opt/arc3/sgl/sglang_commit.txt
(cd fork && git log -1 --format='%H %cd') | tee /opt/arc3/sgl/fork_commit.txt
cp fork/hot_tokens_64k.pt /opt/arc3/sgl/hot_tokens_64k.pt
cd /opt/arc3
cat > /opt/arc3/sgl/build.sh <<'SGLBUILD'
#!/bin/bash
set -euo pipefail
nvidia-smi -L
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq python3.12 python3.12-venv python3.12-dev git build-essential gcc-13 g++-13 curl ninja-build cmake pkg-config >/dev/null
curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1
curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal >/dev/null 2>&1
export PATH=/root/.local/bin:/root/.cargo/bin:/usr/local/cuda/bin:$PATH
export CUDA_HOME=/usr/local/cuda CUDACXX=/usr/local/cuda/bin/nvcc CC=gcc-13 CXX=g++-13 CUDAHOSTCXX=g++-13 TORCH_CUDA_ARCH_LIST=12.0
cd /sgl/sglang-official
git config user.email arc3@arc3 && git config user.name arc3
applied=0
for p in 0002-fp8-qsa-tile-dequant 0003-sm120-fp32-prefill-state 0001b-recoverssm-wy-sm120-PORTED; do
  git apply --exclude='test/*' ../fork/patches/$p.patch && applied=$((applied+1))
done
for p in 0004-sm120-lowm-triton-gemm 0005-sm120-fp8-weight-only 0006-sm120-fp8-hc-lmhead; do
  git am ../fork/patches/$p.patch && applied=$((applied+1))
done
test "$applied" = 6
git log -1 --format='%H' > /sgl/patched_commit.txt
uv venv --python 3.12 /opt/sglvenv >/dev/null && source /opt/sglvenv/bin/activate
export MAX_JOBS=16 CMAKE_BUILD_PARALLEL_LEVEL=16 CARGO_BUILD_JOBS=16
uv pip install --prerelease=allow --index-strategy unsafe-best-match --extra-index-url https://docs.sglang.ai/whl/cu130/ -e python > /sgl/install.log 2>&1
python -c "import sglang, torch; print('sglang', sglang.__version__, 'torch', torch.__version__, torch.version.cuda)" | tee /sgl/versions.txt
SGLBUILD
cat > /opt/arc3/sgl/serve.sh <<'SGLSERVE'
#!/bin/bash
# argv keeps the vLLM flag names the runtime probe reads back from `docker inspect flashnext` (Config.Cmd).
set -uo pipefail
MEMFRAC=""; KVD=""; CTX=""; LANES=""
while [ $# -gt 0 ]; do
  case "$1" in
    --gpu-memory-utilization) MEMFRAC=$2; shift 2;;
    --kv-cache-dtype) KVD=$2; shift 2;;
    --max-model-len) CTX=$2; shift 2;;
    --max-num-seqs) LANES=$2; shift 2;;
    *) echo "serve.sh: unknown argument $1"; exit 2;;
  esac
done
test -n "$MEMFRAC" && test -n "$KVD" && test -n "$CTX" && test -n "$LANES"
source /opt/sglvenv/bin/activate
export PATH=/root/.local/bin:/root/.cargo/bin:/usr/local/cuda/bin:$PATH
export CUDA_HOME=/usr/local/cuda CUDACXX=/usr/local/cuda/bin/nvcc CC=gcc-13 CXX=g++-13 CUDAHOSTCXX=g++-13 TORCH_CUDA_ARCH_LIST=12.0
CACHE=/sgl/cache; mkdir -p $CACHE/huggingface $CACHE/torchinductor $CACHE/triton $CACHE/flashinfer $CACHE/sglang/jit
export HF_HOME=$CACHE/huggingface XDG_CACHE_HOME=$CACHE TORCHINDUCTOR_CACHE_DIR=$CACHE/torchinductor TRITON_CACHE_DIR=$CACHE/triton
export FLASHINFER_WORKSPACE_BASE=$CACHE/flashinfer SGLANG_JIT_CACHE_DIR=$CACHE/sglang/jit
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN=1 OMP_NUM_THREADS=8 TOKENIZERS_PARALLELISM=false
export MAX_JOBS=4 CMAKE_BUILD_PARALLEL_LEVEL=4 FLASHINFER_NINJA_JOBS=4 FLASHINFER_NVCC_THREADS=2 TORCHINDUCTOR_COMPILE_THREADS=4
export SGLANG_SM120_LOWM_FP8_WEIGHT=1 SGLANG_SM120_LM_HEAD_FP8=1 HF_HUB_OFFLINE=1
exec python -m sglang.launch_server --model-path /model --load-format safetensors --served-model-name "$SERVED_MODEL_NAME" \
  --host 127.0.0.1 --port 1235 --tp 1 --dtype bfloat16 --quantization modelopt_fp4 \
  --mem-fraction-static "$MEMFRAC" --context-length "$CTX" --kv-cache-dtype "$KVD" --page-size 64 \
  --max-running-requests "$LANES" --cuda-graph-max-bs "$LANES" --chunked-prefill-size 4096 \
  --mamba-ssm-dtype bfloat16 --max-mamba-cache-size 48 --mamba-radix-cache-strategy extra_buffer --mamba-track-interval 64 \
  --linear-attn-decode-backend flashinfer --linear-attn-prefill-backend flashinfer \
  --ple-offload-embedding --trust-remote-code --chat-template /model/chat_template.jinja \
  --reasoning-parser qwen3 --tool-call-parser qwen3_coder --enable-metrics --watchdog-timeout 1800 \
  --speculative-algorithm NEXTN --speculative-num-steps 3 --speculative-eagle-topk 1 --speculative-num-draft-tokens 4 \
  --speculative-draft-model-quantization unquant --speculative-token-map /sgl/hot_tokens_64k.pt --gdn-mtp-cache-mode none \
  --speculative-accept-threshold-single 1.0 --speculative-accept-threshold-acc 1.0 \
  --enable-hierarchical-cache --hicache-size __HICACHE_GB__ --hicache-write-policy write_through --hicache-io-backend kernel --hicache-mem-layout page_first
SGLSERVE
docker pull -q "$SGL_IMAGE_BASE"
docker run --rm --gpus all "$SGL_IMAGE_BASE" nvidia-smi -L
docker rm -f sglbuild >/dev/null 2>&1 || true
docker run --name sglbuild --gpus all --network=host -v /opt/arc3/sgl:/sgl "$SGL_IMAGE_BASE" bash /sgl/build.sh
docker commit sglbuild "$SGL_IMAGE" >/dev/null
docker rm sglbuild >/dev/null
cp /opt/arc3/sgl/versions.txt /opt/arc3/sglang-versions.txt

# Immutable, checksummed GCS mirror attestation (unchanged model payload; golden image carries it).
MODEL_GCS_PREFIX='gs://cellens-ai-artifacts/arc3-duck/models/qwen3.8-flash-next-nvfp4-radixark/7b719225242aacd3dbd3f9407468c2ee9a9d2594'
gcloud storage cp "$MODEL_GCS_PREFIX/_mirror/DONE" /opt/arc3/model-mirror-done.json
gcloud storage cp "$MODEL_GCS_PREFIX/_mirror/MANIFEST.json" /opt/arc3/model-mirror-manifest.json
if [ -n "$GOLDEN_RUNTIME_IMAGE" ]; then
  printf 'golden runtime image %s: immutable model payload reused\n' "$GOLDEN_RUNTIME_IMAGE" | \
    tee /opt/arc3/model-download.log
else
  gcloud storage rsync --recursive "$MODEL_GCS_PREFIX" "$MODEL_DIR" \
    2>&1 | tee /opt/arc3/model-download.log
fi
ARC3_GOLDEN_RUNTIME_IMAGE="$GOLDEN_RUNTIME_IMAGE" /opt/arc3/pysrv/bin/python - <<'PYVERIFY'
import hashlib
import json
import os
from pathlib import Path

model_id = "RadixArk/Qwen3.8-Flash-Next-NVFP4"
revision = "7b719225242aacd3dbd3f9407468c2ee9a9d2594"
manifest = json.loads(Path("/opt/arc3/model-mirror-manifest.json").read_text(encoding="utf-8"))
assert manifest["model_id"] == model_id
assert manifest["revision"] == revision
assert manifest["resolved_revision"] == revision
assert manifest["file_count"] == len(manifest["files"])
assert manifest["total_bytes"] == sum(row["size"] for row in manifest["files"])
for row in manifest["files"]:
    path = Path("/opt/arc3/flashnext-model") / row["path"]
    assert path.is_file(), f"missing mirrored model file: {row['path']}"
    assert path.stat().st_size == row["size"], f"size drift: {row['path']}"
    if not os.environ.get("ARC3_GOLDEN_RUNTIME_IMAGE"):
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(16 * 1024 * 1024), b""):
                digest.update(block)
        assert digest.hexdigest() == row["sha256"], f"sha256 drift: {row['path']}"
print(
    "golden image size-manifest attestation passed"
    if os.environ.get("ARC3_GOLDEN_RUNTIME_IMAGE")
    else "full model SHA-256 verification passed",
    flush=True,
)
PYVERIFY
/opt/arc3/pysrv/bin/python - <<'PYINFO'
import json
with open("/opt/arc3/flashnext-model/download-info.json", "w", encoding="utf-8") as fh:
    json.dump({
        "model_id": "RadixArk/Qwen3.8-Flash-Next-NVFP4",
        "revision": "7b719225242aacd3dbd3f9407468c2ee9a9d2594",
        "source": "gs://cellens-ai-artifacts/arc3-duck/models/qwen3.8-flash-next-nvfp4-radixark/7b719225242aacd3dbd3f9407468c2ee9a9d2594/",
        "verified_from_manifest": True,
    }, fh, indent=2)
PYINFO
/opt/arc3/pysrv/bin/python - <<'PYINFO'
import json
from pathlib import Path

root = Path("/opt/arc3/flashnext-model")
download = json.loads((root / "download-info.json").read_text())
info = {
    **download,
    "quantization": "RadixArk NVFP4 routed experts; served by SGLang (sglang-flashnext-sm120 patches: fp8 KV, fp8 weight copies, fp8 QSA tile dequant)",
    "serving": "sglang",
    "sglang_commit": Path("/opt/arc3/sgl/sglang_commit.txt").read_text().strip(),
    "sglang_fork_commit": Path("/opt/arc3/sgl/fork_commit.txt").read_text().strip(),
    "sglang_patched_commit": Path("/opt/arc3/sgl/patched_commit.txt").read_text().strip(),
    "mtp_enabled": True,
    "speculative": "NEXTN k=3, 4 draft tokens, lossless acceptance, FR-Spec 64k token map",
    "hierarchical_host_cache_gb": __HICACHE_GB__,
    "requested_server_sequences": __SLOTS__,
    "games_in_flight": __LANES__,
    "context_length": __CTX__,
}
Path("/opt/arc3/model-info.json").write_text(json.dumps(info, indent=2) + "\n")
PYINFO

# vLLM-compat shim in front of SGLang: the harness needs /tokenize (messages+tools+images -> {count, max_model_len}),
# max_model_len on /v1/models, and preserve_thinking as a default chat-template kwarg (vLLM had it server-side).
cat > /opt/arc3/sgl_proxy.py <<'PYPROXY'
import json, sys, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
LISTEN, UPSTREAM, MAX_MODEL_LEN = int(sys.argv[1]), sys.argv[2], int(sys.argv[3])
HOP = {"connection", "keep-alive", "transfer-encoding", "content-length", "host", "accept-encoding"}
DEFAULT_MODEL = [None]

def with_defaults(payload):
    kw = dict(payload.get("chat_template_kwargs") or {})
    kw.setdefault("preserve_thinking", True)
    payload["chat_template_kwargs"] = kw
    return payload

class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""
    def _send(self, code, payload, ctype="application/json"):
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload)
    def _upstream(self, method, path, body, headers, timeout=3600):
        req = urllib.request.Request(UPSTREAM + path, data=body if body else None, method=method)
        for k, v in headers.items():
            if k.lower() not in HOP: req.add_header(k, v)
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            return e
    def _stream(self, r):
        self.send_response(r.code if hasattr(r, "code") else r.status)
        for k, v in r.headers.items():
            if k.lower() not in HOP: self.send_header(k, v)
        self.send_header("Transfer-Encoding", "chunked"); self.end_headers()
        while True:
            chunk = r.read(65536)
            if not chunk: break
            self.wfile.write(b"%x\r\n" % len(chunk) + chunk + b"\r\n"); self.wfile.flush()
        self.wfile.write(b"0\r\n\r\n")
    def _passthrough(self, method):
        body = self._body()
        self._stream(self._upstream(method, self.path, body, dict(self.headers)))
    def _model(self):
        if DEFAULT_MODEL[0] is None:
            data = json.loads(self._upstream("GET", "/v1/models", None, {}).read())
            DEFAULT_MODEL[0] = data["data"][0]["id"]
        return DEFAULT_MODEL[0]
    def do_GET(self):
        if self.path.split("?")[0] in ("/v1/models", "/models"):
            r = self._upstream("GET", "/v1/models", None, {})
            data = json.loads(r.read())
            for row in data.get("data", []): row["max_model_len"] = MAX_MODEL_LEN
            return self._send(200, json.dumps(data).encode())
        return self._passthrough("GET")
    def do_POST(self):
        route = self.path.split("?")[0]
        if route == "/tokenize":
            payload = json.loads(self._body() or b"{}")
            model = payload.get("model") or self._model()
            if "messages" in payload:
                msgs = []
                for m in payload["messages"]:   # the harness counts with the vLLM alias `reasoning`; render it as the completion will
                    m = dict(m)
                    if m.get("reasoning") is not None and m.get("reasoning_content") is None:
                        m["reasoning_content"] = m.pop("reasoning")
                    msgs.append(m)
                fwd = {"model": model, "messages": msgs, "max_tokens": 1, "temperature": 0.0, "stream": False}
                if payload.get("tools"): fwd["tools"] = payload["tools"]
                if payload.get("chat_template_kwargs") is not None: fwd["chat_template_kwargs"] = payload["chat_template_kwargs"]
                fwd = with_defaults(fwd)
                r = self._upstream("POST", "/v1/chat/completions", json.dumps(fwd).encode(), {"Content-Type": "application/json"}, timeout=900)
            else:
                fwd = {"model": model, "prompt": payload.get("prompt", ""), "max_tokens": 1, "temperature": 0.0, "stream": False}
                r = self._upstream("POST", "/v1/completions", json.dumps(fwd).encode(), {"Content-Type": "application/json"}, timeout=900)
            raw = r.read()
            if (r.code if hasattr(r, "code") else r.status) != 200:
                return self._send(502, raw)
            n = json.loads(raw)["usage"]["prompt_tokens"]
            return self._send(200, json.dumps({"count": int(n), "max_model_len": MAX_MODEL_LEN, "tokens": []}).encode())
        if route in ("/v1/chat/completions", "/chat/completions"):
            body = self._body()
            try:
                payload = json.loads(body or b"{}")
            except ValueError:
                payload = None
            if isinstance(payload, dict):
                body = json.dumps(with_defaults(payload)).encode()
            r = self._upstream("POST", self.path, body, {k: v for k, v in self.headers.items() if k.lower() != "content-length"})
            return self._stream(r)
        return self._passthrough("POST")

ThreadingHTTPServer.daemon_threads = True
ThreadingHTTPServer(("127.0.0.1", LISTEN), H).serve_forever()
PYPROXY

'''.replace("__HICACHE_GB__", str(HICACHE_GB)).replace("__LANES__", str(LANES)).replace("__SLOTS__", str(SLOTS)).replace("__CTX__", str(CTX))
s = s[:cut_a] + sgl_build + s[cut_b:]

# ---- (2) start_server / wait_server / container_gpu_ready -> SGLang serve container + shim ----
srv_a = s.index("start_server() {")
srv_b = s.index('echo "$KV_DTYPE_USED" > /opt/arc3/kv-dtype-used.txt')
sgl_serve = r'''start_server() {
  local kv_dtype="$1"
  docker rm -f flashnext >/dev/null 2>&1 || true
  pkill -f "docker logs -f flashnext" >/dev/null 2>&1 || true
  pkill -f sgl_proxy.py >/dev/null 2>&1 || true
  : > /opt/arc3/vllm.log
  # --privileged: Spot hosts have revoked the container's GPU cgroup rule mid-run ("Failed to initialize NVML: Unknown Error").
  docker run -d --name flashnext --hostname arc3-vllm --privileged --gpus all --ipc=host --network=host \
    --ulimit memlock=-1 \
    -e SERVED_MODEL_NAME="$SERVED_MODEL_NAME" \
    -v /opt/arc3/sgl:/sgl \
    -v "$MODEL_DIR:/model:ro" \
    "$SGL_IMAGE" bash /sgl/serve.sh \
    --gpu-memory-utilization __MEMFRAC__ --kv-cache-dtype "$kv_dtype" \
    --max-model-len __CTX__ --max-num-seqs __SLOTS__
  nohup docker logs -f flashnext > /opt/arc3/vllm.log 2>&1 &
  nohup /opt/arc3/pysrv/bin/python /opt/arc3/sgl_proxy.py 1234 http://127.0.0.1:1235 __CTX__ > /opt/arc3/sgl-proxy.log 2>&1 &
}

wait_server() {
  # weights ~7 min + MTP CUDA graph capture ~13 min on this card
  for _ in $(seq 1 240); do
    if curl -sf -m 3 http://127.0.0.1:1235/health >/dev/null && curl -sf -m 3 http://127.0.0.1:1234/v1/models | grep -q max_model_len; then return 0; fi
    docker inspect -f '{{.State.Running}}' flashnext 2>/dev/null | grep -qx true || return 1
    sleep 10
  done
  return 1
}

# Experimental KV choice is explicit. No fallback to a different profile.
container_gpu_ready() {
  docker run --rm --gpus all "$SGL_IMAGE_BASE" nvidia-smi -L
}

if ! container_gpu_ready; then
  sleep 10
  container_gpu_ready
fi
KV_DTYPE_USED=fp8_e4m3
start_server "$KV_DTYPE_USED"
if ! wait_server; then
  cp /opt/arc3/vllm.log /opt/arc3/vllm-start-attempt1.log
  sleep 10
  container_gpu_ready
  start_server "$KV_DTYPE_USED"
fi
if ! wait_server; then
  echo "SGLang failed to serve the requested profile" | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"
  sync_all
  exit 1
fi
'''.replace("__MEMFRAC__", MEMFRAC).replace("__LANES__", str(LANES)).replace("__SLOTS__", str(SLOTS)).replace("__CTX__", str(CTX))
s = s[:srv_a] + sgl_serve + s[srv_b:]

# ---- (3) serving-environment capture: the container python is the SGLang venv ----
s = litn('docker exec -i flashnext "$CONTAINER_PYTHON" - <<\'PYVERS\'', "docker exec -i flashnext /opt/sglvenv/bin/python - <<'PYVERS'", s, 2)
s = litn("import vllm" + NL, "import sglang" + NL, s, 2)
s = litn('print("vllm", vllm.__version__)', 'print("sglang", sglang.__version__)', s, 2)

# ---- (4) smoke test lane count ----
if LANES != OLD_LANES:
    s = lit1("with concurrent.futures.ThreadPoolExecutor(max_workers=7) as pool:" + NL + "    capacity = list(pool.map(capacity_call, range(7)))",
             f"with concurrent.futures.ThreadPoolExecutor(max_workers={LANES}) as pool:" + NL + f"    capacity = list(pool.map(capacity_call, range({LANES})))", s)
    s = lit1('    "max_num_seqs": 7,', f'    "max_num_seqs": {LANES},', s)
s = lit1('    "mtp_enabled": False,' + NL + '    "max_num_seqs"', '    "mtp_enabled": True,' + NL + '    "max_num_seqs"', s)

# ---- (5) vLLM native-context capacity gate -> SGLang serving gate ----
gate_a = s.index(f"# Native 7x{OLD_CTX} acceptance runs on this GPU and must finish before gameplay.")
gate_b = s.index("sync_all" + NL + NL + "# Install the pinned environment and run the experimental candidate on all 25 games.")
serving_gate = r'''# SGLang serving gate. Replaces the vLLM native-context capacity gate (it reads vllm:* prefix-cache metrics that do
# not exist here). Tests what actually risks this arm: LANES concurrent long-prefix completions, a vision request, a
# tool call that comes back parsed, and /tokenize == usage.prompt_tokens on text+tools, an image, and the selftest
# fixture (4 x 1024px images + reasoning history rendered through the `reasoning` alias).
/opt/arc3/pysrv/bin/python - <<'PYSGLGATE' 2>&1 | tee /opt/arc3/sglang-serving-gate.log
import base64, json, struct, time, urllib.request, zlib
from concurrent.futures import ThreadPoolExecutor
URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL = "RadixArk/Qwen3.8-Flash-Next-NVFP4"
LANES = __LANES__

def post(payload, timeout=900):
    req = urllib.request.Request(URL, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    started = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        body = json.load(fh)
    return body, time.monotonic() - started

filler = "The board is a grid. " * 3000
def long_call(index):
    body, seconds = post({"model": MODEL, "max_tokens": 32, "temperature": 0.7, "top_p": 0.95,
                          "chat_template_kwargs": {"enable_thinking": False},
                          "messages": [{"role": "user", "content": f"Probe {index}. {filler} Reply OK."}]})
    return {"index": index, "seconds": seconds, "ok": bool(body.get("choices"))}

started = time.monotonic()
with ThreadPoolExecutor(max_workers=LANES) as pool:
    concurrent = list(pool.map(long_call, range(LANES)))
concurrent_seconds = time.monotonic() - started

# the 1x1 PNG the startup smoke test already sends successfully (the 2x2 hex blob from the llama.cpp arm is not a valid PNG: SGLang 400s it)
png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
base64.b64decode(png)
vision, vision_seconds = post({"model": MODEL, "max_tokens": 24, "temperature": 0.7, "chat_template_kwargs": {"enable_thinking": False}, "messages": [
    {"role": "user", "content": [{"type": "text", "text": "Name one colour in this image."},
                                 {"type": "image_url", "image_url": {"url": "data:image/png;base64," + png}}]}]})

tools = [{"type": "function", "function": {
    "name": "python", "description": "Run a Python snippet against the current game.",
    "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}}}]
tool_body, tool_seconds = post({"model": MODEL, "max_tokens": 512, "temperature": 0.7, "tools": tools,
                                "chat_template_kwargs": {"enable_thinking": False}, "messages": [
    {"role": "user", "content": "Call the python tool with code that sets result to 2+2. Do not answer in text."}]})
message = tool_body["choices"][0]["message"]
tool_calls = message.get("tool_calls") or []

def count_tokens(messages, tools=None):
    body = {"model": MODEL, "messages": messages, "add_generation_prompt": True, "chat_template_kwargs": {"enable_thinking": False}}
    if tools: body["tools"] = tools
    req = urllib.request.Request(URL.replace("/v1/chat/completions", "/tokenize"), data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as fh:
        data = json.load(fh)
    assert data["max_model_len"] == __CTX__, data
    return data["count"]
def usage_tokens(messages, tools=None):
    body = {"model": MODEL, "messages": messages, "max_tokens": 1, "temperature": 0.0, "chat_template_kwargs": {"enable_thinking": False}}
    if tools: body["tools"] = tools
    return post(body)[0]["usage"]["prompt_tokens"]
text_msgs = [{"role": "system", "content": "You play a grid game."}, {"role": "user", "content": "Probe. " + filler[:4000] + " Reply OK."}]
img_msgs = [{"role": "user", "content": [{"type": "text", "text": "Name one colour in this image."},
                                          {"type": "image_url", "image_url": {"url": "data:image/png;base64," + png}}]}]
tok_text, use_text = count_tokens(text_msgs, tools), usage_tokens(text_msgs, tools)
tok_img, use_img = count_tokens(img_msgs), usage_tokens(img_msgs)
def png_rgb(w, h, rgb=(0, 0, 0)):
    raw = b''.join(bytes([0]) + bytes(rgb) * w for _ in range(h))
    def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    sig = bytes([137, 80, 78, 71, 13, 10, 26, 10])
    return sig + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b'')
big = base64.b64encode(png_rgb(1024, 1024)).decode()
fixture = [{'role': 'system', 'content': 'You play a grid game.'}]
for i in range(4):
    fixture += [{'role': 'user', 'content': [{'type': 'text', 'text': 'Synthetic frame ' + str(i)}, {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + big}}]},
                {'role': 'assistant', 'content': 'Observed.', 'reasoning_content': 'The red square stayed in place.'}]
fixture.append({'role': 'user', 'content': 'Validation only. Reply OK.'})
aliased = [({**m, 'reasoning': m['reasoning_content']} if 'reasoning_content' in m else m) for m in fixture]
for m in aliased: m.pop('reasoning_content', None)
tok_fix, use_fix = count_tokens(aliased, tools), usage_tokens(fixture, tools)
report = {
    "tokenize_text_tools": [tok_text, use_text], "tokenize_image": [tok_img, use_img], "tokenize_selftest_fixture": [tok_fix, use_fix],
    "concurrent_requests": len(concurrent), "concurrent_wall_seconds": round(concurrent_seconds, 1),
    "all_concurrent_returned": all(x["ok"] for x in concurrent),
    "slowest_concurrent_seconds": round(max(x["seconds"] for x in concurrent), 1),
    "vision_seconds": round(vision_seconds, 1),
    "vision_returned": bool(vision.get("choices")),
    "tool_seconds": round(tool_seconds, 1),
    "tool_calls_parsed": len(tool_calls),
    "tool_call_name": (tool_calls[0]["function"]["name"] if tool_calls else None),
    "tool_call_markup_in_content": "<tool_call>" in str(message.get("content") or ""),
    "serving": "sglang", "lanes": LANES, "context": __CTX__,
}
print(json.dumps(report, indent=2), flush=True)
with open("/opt/arc3/sglang-serving-gate.json", "w", encoding="utf-8") as fh:
    json.dump(report, fh, indent=2)
assert report["all_concurrent_returned"], "concurrent long-prefix completions failed"
assert report["vision_returned"], "vision request failed; the harness sends current_grid images"
assert report["tool_calls_parsed"] >= 1, "no parsed tool call came back; the harness cannot act"
assert tok_text == use_text, ("/tokenize count differs from usage.prompt_tokens (text+tools)", tok_text, use_text)
assert tok_img == use_img, ("/tokenize count differs from usage.prompt_tokens (image)", tok_img, use_img)
assert tok_fix == use_fix, ("/tokenize count differs from usage.prompt_tokens (selftest fixture: 4 x 1024px image + reasoning)", tok_fix, use_fix)
PYSGLGATE
timeout 15 gcloud storage cp /opt/arc3/sglang-serving-gate.json "$BUCKET/$RUN_ID/sglang-serving-gate.json" || true
'''.replace("__LANES__", str(LANES)).replace("__CTX__", str(CTX))
s = s[:gate_a] + serving_gate + s[gate_b:]

# ---- (6) the rest of the context / lane pins (as in derive_c60k_mtp.py) ----
if LANES != OLD_LANES:
    s = sub1(rf"export ARC3_MAX_RUNTIME_S_PER_GAME={OLD_GAME_S}$", f"export ARC3_MAX_RUNTIME_S_PER_GAME={GAME_S}", s, re.M)
    s = sub1(r"export ARC3_BENCHMARK_CONCURRENCY=7$", f"export ARC3_BENCHMARK_CONCURRENCY={LANES}", s, re.M)
    s = sub1(rf"assert os\.environ\['ARC3_MAX_RUNTIME_S_PER_GAME'\] == '{OLD_GAME_S}'", f"assert os.environ['ARC3_MAX_RUNTIME_S_PER_GAME'] == '{GAME_S}'", s)
    s = sub1(r"assert os\.environ\['ARC3_BENCHMARK_CONCURRENCY'\] == '7'", f"assert os.environ['ARC3_BENCHMARK_CONCURRENCY'] == '{LANES}'", s)
s = subn(rf"export LOCAL_ANALYZER_CONTEXT_WINDOW={OLD_CTX}", f"export LOCAL_ANALYZER_CONTEXT_WINDOW={CTX}", s, 2)
s = sub1(rf'--live --arm baseline --model "\$SERVED_MODEL_NAME" --context {OLD_CTX} ', f'--live --arm baseline --model "$SERVED_MODEL_NAME" --context {CTX} ', s)
s = sub1(rf"--live --context {OLD_CTX} --base-url", f"--live --context {CTX} --base-url", s)
s = sub1(rf"assert os\.environ\['LOCAL_ANALYZER_CONTEXT_WINDOW'\] == '{OLD_CTX}'", f"assert os.environ['LOCAL_ANALYZER_CONTEXT_WINDOW'] == '{CTX}'", s)
s = sub1(rf"assert agent\._context_budget_tokens == {OLD_BUDGET}", f"assert agent._context_budget_tokens == {BUDGET}", s)
s = sub1(rf"assert renderer\['context'\] == {OLD_CTX}", f"assert renderer['context'] == {CTX}", s)
s = sub1(rf"assert renderer\['input_budget'\] == {OLD_BUDGET}", f"assert renderer['input_budget'] == {BUDGET}", s)

# ---- (7) PYCAPACITYFINAL re-reads the vLLM gate report -> the SGLang serving gate is the capacity evidence ----
cap_old = f"""report = json.loads(Path('/opt/arc3/native-context-capacity-gate.json').read_text())
assert report['status'] == 'passed', report.get('status')
assert report['configuration']['context'] == {OLD_CTX}
assert report['configuration']['concurrency'] == 7
assert report['gates']['native_capacity_and_reuse_pass'] is True
assert report['gates']['zero_preemptions_verified'] is True
assert report['gates']['server_concurrency_observed'] is True
assert report['script_sha256'] == '13fe2cd4a9cf545cfffaa6e3932250433389b541221b745327c87b7e1b33da39'
"""
cap_new = f"""report = json.loads(Path('/opt/arc3/sglang-serving-gate.json').read_text())   # SGLang arm: the serving gate is the capacity evidence
assert report['serving'] == 'sglang' and report['lanes'] == {LANES} and report['context'] == {CTX}
assert report['concurrent_requests'] == {LANES} and report['all_concurrent_returned'] is True
assert report['vision_returned'] is True and report['tool_calls_parsed'] >= 1
assert report['tokenize_text_tools'][0] == report['tokenize_text_tools'][1]
assert report['tokenize_image'][0] == report['tokenize_image'][1]
assert report['tokenize_selftest_fixture'][0] == report['tokenize_selftest_fixture'][1]
"""
s = lit1(cap_old, cap_new, s)

# ---- (8) prefix reset + vLLM metrics sampler -> SGLang flush_cache + a generic /metrics sampler ----
reset_start = "# Clear synthetic fixtures only after all live gates and warmup have settled."
sampler_end = 'kill -0 "$METRICS_SAMPLER_PID"' + NL
ra = s.index(reset_start); rb = s.index(sampler_end) + len(sampler_end)
s = s[:ra] + r'''# Clear synthetic fixtures only after all live gates and warmup have settled (SGLang: /flush_cache drops the radix tree).
curl -sf -m 30 -X POST http://127.0.0.1:1235/flush_cache > /opt/arc3/native-context-prefix-reset.log 2>&1 || true
# SGLang exposes Prometheus counters at /metrics under sglang:* names; sample them every 30 s like the vLLM sampler did.
( while true; do
    printf '{"utc":"%s","body":%s}\n' "$(date -u +%FT%TZ)" \
      "$(curl -s -m 5 http://127.0.0.1:1235/metrics | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '""')" \
      >> /opt/arc3/work/sglang-metrics.jsonl
    sleep 30
  done ) > /opt/arc3/work/sglang-metrics-sampler.log 2>&1 &
METRICS_SAMPLER_PID=$!
sleep 2
test -s /opt/arc3/work/sglang-metrics.jsonl
kill -0 "$METRICS_SAMPLER_PID"
''' + s[rb:]
s = lit1("""    http://127.0.0.1:1234/metrics \\
    | grep -E '^vllm:(prefix_cache_|external_prefix_cache_|num_preemptions_|kv_cache_usage_|num_requests_)' \\""",
         """    http://127.0.0.1:1235/metrics \\
    | grep -E '^sglang:' \\""", s)

# ---- (8a) half-context swap off: env, skip the live gate (write the receipt the probe reads), keep the unit tests ----
if not SWAP:
    s = lit1("export ARC3_HALF_CONTEXT_SWAP=1" + NL, "export ARC3_HALF_CONTEXT_SWAP=0   # no 50% swap: oldest-turn trimming at the budget" + NL, s)
    s = lit1("timeout --kill-after=10 300 ./.venv/bin/python -B /opt/arc3/execution-selftest/live_half_swap_gate.py 2>&1 | tee /opt/arc3/half-swap-live-gate.log",
             "echo '{\"status\": \"skipped\", \"half_swap\": \"off\"}' | tee /opt/arc3/half-swap-live-gate.json /opt/arc3/half-swap-live-gate.log", s)
# ---- (8b) telemetry upload list: the vLLM gate/prefix-reset files are replaced by the SGLang gate + flush log ----
s = lit1("native-context-prefix-reset.json native-context-prefix-reset.log native-context-capacity-gate.json native-context-capacity-gate.log",
         "native-context-prefix-reset.log sglang-serving-gate.json sglang-serving-gate.log sglang-versions.txt sgl-proxy.log", s)

# ---- (9) pins, hashes, env, watchdog ----
s = sub1(re.escape(f"echo '{old_candidate_sha}  /tmp/bundle.tgz'"), f"echo '{candidate_sha}  /tmp/bundle.tgz'", s)
s = sub1(re.escape(f"echo '{old_runner_sha}  /opt/arc3/v12_run.py'"), f"echo '{runner_sha}  /opt/arc3/v12_run.py'", s)
src_code = re.search(r"gs://cellens-ai-artifacts/arc3-duck/code/([a-z0-9-]+)/[0-9a-f]{64}/runtime_probe\.py", s).group(1)
for old, new, fn in ((old_probe_sha, probe_sha, "runtime_probe.py"), (old_cfg_sha, cfg_sha, "CONFIG_FLAGS.json"), (old_adapter_sha, adapter_sha, "ADAPTER.json")):
    s = sub1(re.escape(f"gs://cellens-ai-artifacts/arc3-duck/code/{src_code}/{old}/{fn}"), f"{BUCKET_CODE}/{new}/{fn}", s)
    s = sub1(re.escape(f"echo '{old}  /opt/arc3/config-audit/{fn}'"), f"echo '{new}  /opt/arc3/config-audit/{fn}'", s)
s = sub1(re.escape(f"echo '{old_selftest_sha}  /tmp/execution-selftest.tgz'"), f"echo '{selftest_sha}  /tmp/execution-selftest.tgz'", s)
s = sub1(re.escape(f"echo '{old_release_sha}  /opt/arc3/execution-release-manifest.json'"), f"echo '{release_sha}  /opt/arc3/execution-release-manifest.json'", s)
s = sub1(r"^export ARC3_PROMPT_ABLATE_LOOP=0$", "export ARC3_PROMPT_ABLATE_LOOP=0" + NL + f"export ARC3_SERVING_SPECULATIVE=sglang-nextn3-c{CTX}-w{LANES}", s, re.M)
s = add_watchdog(s)
old_req = re.search(r"requestId=([0-9a-f-]{36})", s).group(1); new_req = str(uuid.uuid4())
s = s.replace(old_req, new_req); (ARM / "DELETE_REQUEST_ID").write_text(new_req)

assert str(OLD_CTX) not in s, [s[max(0, m.start() - 60):m.start() + 40] for m in re.finditer(str(OLD_CTX), s)]
assert str(OLD_BUDGET) not in s
if LANES != OLD_LANES: assert "2061" not in s and "CONCURRENCY=7" not in s
for bad in ("vllm/vllm-openai", "VLLM_PLE_CPU_OFFLOAD", "ple_layer_native_fp8", "scheduler-overlay", "retention-overlay", "CONTAINER_PYTHON",
            "capacity_gate.py", "reset_idle_cache.py", "vllm_metrics_sampler", "--cudagraph-capture-sizes", "--max-num-batched-tokens",
            "native-context-capacity-gate.json", "'^vllm:", "import vllm"):
    assert bad not in s, bad
for must in ("arc3-sglang:built", "sgl_proxy.py 1234 http://127.0.0.1:1235", "sglang-serving-gate.json", "--speculative-algorithm NEXTN",
             f"--hicache-size {HICACHE_GB}", f"--max-model-len {CTX} --max-num-seqs {SLOTS}", f"--gpu-memory-utilization {MEMFRAC}",
             "ARC3_ACTION_CAP_MODE=return", "test_half_swap.py", "WATCHDOG_PID", *(("ARC3_CONTEXT_COMPACTION=1",) if SRC_KIND == "cv5cr" else ()),
             *(("live_half_swap_gate.py", "ARC3_HALF_CONTEXT_SWAP=1") if SWAP else ("ARC3_HALF_CONTEXT_SWAP=0",)),
             "flush_cache", "docker stop -t 20 flashnext"):
    assert must in s, must
for must in ("attest_prompt", "'docker','inspect','flashnext'", "half-swap-live-gate.json", f"'--max-model-len')+1]=='{CTX}'"):
    assert must in p, must
(ARM / "startup.sh").write_text(s, encoding="utf-8", newline=NL)
(ARM / "META_KEYS.json").write_text(json.dumps(sorted(set(re.findall(r"meta ([a-z0-9-]+)", s))), indent=1))
shutil.rmtree(work)

# ---------------------------------------------------------------- ARM.json (launch_396.py contract)
pp_sha = re.search(rf"gs://cellens-ai-artifacts/arc3-duck/code/{src_code}/([0-9a-f]{{64}})/prompt_probe\.py", s).group(1)
ep_sha = re.search(rf"gs://cellens-ai-artifacts/arc3-duck/code/{src_code}/([0-9a-f]{{64}})/EXPECTED_PROMPTS\.json", s).group(1)
assert sha_b((ARM / "prompt_probe.py").read_bytes()) == pp_sha and sha_b((ARM / "EXPECTED_PROMPTS.json").read_bytes()) == ep_sha
arm_json = {
    "arm": ARM_NAME, "lanes": LANES, "games": 25, "subset": "", "game_seconds": GAME_S, "suite_minutes": 132, "vm_lifetime_seconds": 14400,
    "provisioning": "SPOT", "source_arm": SRC.name + (" (19-Sep, 132 min)" if SRC_KIND == "cv5cr" else " (17-Sep, 132 min)"), "parent_run_id": PARENT_RUN,
    "context_tokens": CTX, "input_tokens": BUDGET, "slots": SLOTS, "half_context_swap": SWAP, "source_kind": SRC_KIND,
    "serving": f"sglang qwen4-main-squashed + sglang-flashnext-sm120 patches; NEXTN k=3 lossless; fp8 KV; mem {MEMFRAC}; hicache {HICACHE_GB} GB; shim :1234 -> :1235",
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
    "run_id_prefix": cfg["run_id"].rsplit("-", 1)[0], "instance_prefix": f"arc3-g4-{SRC_KIND}sgl{CTX//1024}kw{LANES}" + (f"s{SLOTS}" if SLOTS != LANES else "") + ("" if SWAP else "ns"), "tag": f"{SRC_KIND}sgl",
}
(ARM / "ARM.json").write_text(json.dumps(arm_json, indent=2) + NL)
print(f"{ARM_NAME}: ctx={CTX} budget={BUDGET} lanes={LANES} game_s={GAME_S} config_id={cfg['config_id'][:12]} candidate={candidate_sha[:10]} "
      f"selftest={selftest_sha[:10]} release={release_sha[:10]} runner={runner_sha[:10]} probe={probe_sha[:10]} cfg={cfg_sha[:10]}")
