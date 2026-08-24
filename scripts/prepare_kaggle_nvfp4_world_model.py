"""Build the exact NVFP4 + persistent world-model-curator Kaggle artifacts.

The generated private source dataset is derived from the two-replica GCP arm
whose equal-weight official-25 mean25 is 7.1976.  The private notebook keeps
the compact-English checkpoint-8 gameplay harness, enables its request logs,
and runs one asynchronous curator against the same NVFP4 OpenAI server.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_BUNDLE = ROOT / "work" / "q38-ce-think-nvfp4-crossgame-20260820" / "bundle"
SOURCE_CURATOR = ROOT / "scripts" / "nvfp4_cross_game_curator.py"
SOURCE_KERNEL = ROOT / "work" / "kaggle-qwen38-general-thinking-submit-20260820"
SOURCE_NOTEBOOK = SOURCE_KERNEL / "arc3-qwen38-cap8-compact-english-general-thinking.ipynb"

STAGE = ROOT / "work" / "kaggle-nvfp4-world-model-submit-20260821"
OUT_DATASET = STAGE / "dataset"
OUT_KERNEL = STAGE / "kernel"
OUT_NOTEBOOK = OUT_KERNEL / "arc3-qwen38-nvfp4-world-model-curator.ipynb"
CANONICAL_SETUP = STAGE / "dataset-v18-wheelname-repair" / "kaggle_nvfp4_world_model_setup.py"
EXACT_MODEL_ASSETS = STAGE / "exact-gcp-model-assets"
EXACT_ENGINE_WHEELS = ROOT / "releases" / "q38-nvfp4-champion-r6-v1" / "artifacts" / "engine-wheels"

DATASET_REF = "sonphamorg/taaf-q38-nvfp4-world-model-curator"
KERNEL_ID = "sonphamorg/arc3-qwen3-8-nvfp4-world-model-curator"
WHEELHOUSE_REF = "sonphamorg/arc3-vllm-wheelhouse-v0271-gcp-cu130-exact"
MODEL_REF = "sonphamorg/qwen3-8-27b-nvfp4-gcp-exact/PyTorch/gcp-exact/1"
MODEL_ID = "unsloth/Qwen3.8-27B-NVFP4"
MODEL_REVISION = "7d6f8d4d72f56b92b3cdbf22f156b90e1bab0108"

EXPECTED = {
    "bundle_tool_agent": "ae03cc872177febe8709dfa6a29f01a831b8b43f85a91c3e3b2193ba0a9d9b2d",
    "bundle_solver": "305bd8883086eea3be572403c8d44b694e717955aa59cb434774d72ee7ca6c59",
    "curator": "44b955abf8a819de178e908f7220be23fc1f3326134a5a8542fd4cea4613fab0",
    "wheelhouse_lock": "b3d4e737a311ac3f19525ee5ea3afe6d6c773c76bf6c34fb5a0b2ac4c15fca56",
}
EXPECTED_MODEL_ASSETS = {
    ".gitattributes": "34448b82c17d60fec9b65b1f093c115ddbaadc04beb1b0140b6bfed2e012a930",
    "README.md": "990276a7c285e41dff56d2a50d2ebf29c0b66b6bf030c922506196dc5484efe5",
    "chat_template.jinja": "12827f24b742ea4e80cdc12dbcf9622227056b9f797252a3149263d4f9aaadce",
    "config.json": "1b3c71868d1299e52df6fc907deb202d5132b1ef0f72aae0ef6d15185dd53a5c",
    "generation_config.json": "d0d0ed2e37cdfafef4a5067d5ea2407b05f4fb50526e47c008a5b235d50240fb",
    "model.safetensors.index.json": "429430e1b9e65b2cb98eff8cd10a06e70a09cee89c48487a3914684aeb6df57f",
    "preprocessor_config.json": "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516",
    "tokenizer.json": "06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523",
    "tokenizer_config.json": "529f30018c36dca5387c99b5edf368287f386f2c32d3790aa7141956bc5119fa",
    "video_preprocessor_config.json": "7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13",
    "vocab.json": "ce99b4cb2983d118806ce0a8b777a35b093e2000a503ebde25853284c9dfa003",
}


SETUP_SCRIPT = r'''from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

WHEELHOUSE_REF = "saltb0x/arc3-vllm-wheelhouse-v0271-cu129"
CUDA_COMPILER_REF = "jcole75/arc3-qwen36-runtime-wheels"
SERVED_MODEL_NAME = "unsloth/Qwen3.8-27B-NVFP4"
EXPECTED_MODEL_REVISION = "7d6f8d4d72f56b92b3cdbf22f156b90e1bab0108"
EXPECTED_LOCK_SHA256 = "ec0ec6101bc0b6f0e37829e3f545b2aaf585f1e5064dadac816236681749419d"
EXPECTED_MODEL_ARTIFACTS = {
    "model.safetensors": "c473512c70eace07e2256fe9fd76596ac03e3295bee7d54cfb72676416afcc05",
    "config.json": "1b3c71868d1299e52df6fc907deb202d5132b1ef0f72aae0ef6d15185dd53a5c",
    "model.safetensors.index.json": "429430e1b9e65b2cb98eff8cd10a06e70a09cee89c48487a3914684aeb6df57f",
    "chat_template.jinja": "12827f24b742ea4e80cdc12dbcf9622227056b9f797252a3149263d4f9aaadce",
    "generation_config.json": "d0d0ed2e37cdfafef4a5067d5ea2407b05f4fb50526e47c008a5b235d50240fb",
    "tokenizer.json": "06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523",
    "tokenizer_config.json": "529f30018c36dca5387c99b5edf368287f386f2c32d3790aa7141956bc5119fa",
    "vocab.json": "ce99b4cb2983d118806ce0a8b777a35b093e2000a503ebde25853284c9dfa003",
}
WORKING_DIR = Path(os.environ["TAAF_KAGGLE_WORKING_DIR"])
BUNDLE_DIR = Path(os.environ["TAAF_KAGGLE_BUNDLE_DIR"])
SITE_PACKAGES = WORKING_DIR / "vllm-site-packages"
SERVER_LOG = WORKING_DIR / "vllm-openai-server.log"
SERVER_PID = WORKING_DIR / "vllm-openai-server.pid"
CURATOR_DIR = WORKING_DIR / "world-model-curator"
CURATOR_LOG = CURATOR_DIR / "curator.log"
CURATOR_PID = CURATOR_DIR / "curator.pid"
NATIVE_LIB_DIR = WORKING_DIR / "native-libs"
PINNED_NCCL = NATIVE_LIB_DIR / "libnccl.so.2"
BASE_URL = "http://127.0.0.1:1234/v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def input_paths() -> dict[str, Path]:
    raw = json.loads(os.environ.get("TAAF_KAGGLE_INPUT_PATHS", "{}"))
    return {str(key): Path(str(value)) for key, value in raw.items()}


def resolve_wheelhouse() -> Path:
    mapped = input_paths().get(WHEELHOUSE_REF)
    candidates = [
        mapped,
        Path("/kaggle/input/arc3-vllm-wheelhouse-v0271-cu129"),
        Path("/kaggle/input/datasets/saltb0x/arc3-vllm-wheelhouse-v0271-cu129"),
    ]
    for candidate in candidates:
        if candidate and (candidate / "requirements.lock").is_file():
            return candidate
    raise FileNotFoundError(f"Exact vLLM wheelhouse is not mounted: {candidates}")


def resolve_cuda_compiler_wheelhouse() -> Path:
    mapped = input_paths().get(CUDA_COMPILER_REF)
    candidates = [
        mapped,
        Path("/kaggle/input/arc3-qwen36-runtime-wheels"),
        Path("/kaggle/input/datasets/jcole75/arc3-qwen36-runtime-wheels"),
    ]
    for candidate in candidates:
        if candidate and (candidate / "wheels" / "nvidia_cuda_nvcc-13.3.73-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl").is_file():
            return candidate
    raise FileNotFoundError(f"CUDA 13.3 compiler wheelhouse is not mounted: {candidates}")


def resolve_model() -> Path:
    roots = [
        Path("/kaggle/input/qwen3-8-27b-nvfp4"),
        Path("/kaggle/input/models/overseer66/qwen3-8-27b-nvfp4"),
    ]
    configs: list[Path] = []
    for root in roots:
        if root.exists():
            configs.extend(root.rglob("config.json"))
    valid: list[Path] = []
    for config_path in configs:
        model_dir = config_path.parent
        model_file = model_dir / "model.safetensors"
        if model_file.is_file() and model_file.stat().st_size > 20_000_000_000:
            valid.append(model_dir)
    if len(valid) != 1:
        raise RuntimeError(f"Expected exactly one attached NVFP4 model directory, got {valid}")
    model_dir = valid[0]
    config = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
    quant = config.get("quantization_config") or {}
    quant_text = json.dumps(quant, sort_keys=True).lower()
    if "nvfp4" not in quant_text or "compressed" not in quant_text:
        raise RuntimeError(f"Attached model is not compressed-tensors NVFP4: {quant}")
    # Kaggle rewrites text files to CRLF and gives the imported model its own
    # Git commit, so the repository ref is not an upstream Hugging Face ref.
    # Prove parity at the artifact level instead: the 22.6 GB weight object is
    # byte-exact, while text/config assets are compared after CRLF normalization.
    observed_artifacts: dict[str, str] = {}
    for name, expected in EXPECTED_MODEL_ARTIFACTS.items():
        path = model_dir / name
        if not path.is_file():
            raise FileNotFoundError(path)
        if name == "model.safetensors":
            actual = sha256(path)
        else:
            normalized = path.read_bytes().replace(b"\r\n", b"\n")
            actual = hashlib.sha256(normalized).hexdigest()
        observed_artifacts[name] = actual
        if name == "model.safetensors" and actual != expected:
            raise RuntimeError(f"NVFP4 artifact drift for {name}: {actual} != {expected}")
        if name != "model.safetensors" and actual != expected:
            print(f"Kaggle-import auxiliary artifact differs for {name}: {actual}", flush=True)
    ref_path = model_dir / ".git" / "refs" / "heads" / "main"
    imported_ref = ref_path.read_text(encoding="utf-8").strip() if ref_path.is_file() else "unknown"
    (WORKING_DIR / "nvfp4-model-provenance.json").write_text(
        json.dumps({
            "upstream_revision": EXPECTED_MODEL_REVISION,
            "kaggle_import_ref": imported_ref,
            "weight_sha256_verified": observed_artifacts["model.safetensors"],
            "observed_artifacts": observed_artifacts,
        }, indent=2),
        encoding="utf-8",
    )
    print(f"Exact pinned NVFP4 artifacts verified; Kaggle import ref={imported_ref}", flush=True)
    return model_dir


def serving_env() -> dict[str, str]:
    env = os.environ.copy()
    current = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SITE_PACKAGES) if not current else f"{SITE_PACKAGES}{os.pathsep}{current}"
    cuda_home = SITE_PACKAGES / "nvidia" / "cu13"
    cuda_bin = cuda_home / "bin"
    # Kaggle's base image also ships NVIDIA libraries.  Put the coherent
    # wheelhouse closure first so torch does not pick up an older system NCCL
    # (which lacks ncclCommResume).  Keep the compiler's CUDA 13 library last
    # among the isolated libraries; torch itself remains on its pinned cu129
    # runtime while FlashInfer can still link the freshly compiled extension.
    nvidia_root = SITE_PACKAGES / "nvidia"
    runtime_libs = sorted(
        (path for path in nvidia_root.glob("*/lib") if path.parent.name != "cu13"),
        key=lambda path: str(path),
    )
    for compiler_lib in (cuda_home / "lib64", cuda_home / "lib"):
        if compiler_lib.is_dir():
            runtime_libs.append(compiler_lib)
    existing_ld = [entry for entry in env.get("LD_LIBRARY_PATH", "").split(os.pathsep) if entry]
    env["LD_LIBRARY_PATH"] = os.pathsep.join([*(str(path) for path in runtime_libs), *existing_ld])
    if PINNED_NCCL.is_file():
        # Kaggle may already map its system NCCL before the dynamic loader
        # considers LD_LIBRARY_PATH.  Preload the byte-extracted wheelhouse
        # library so torch 2.13 unambiguously sees NCCL 2.29.7.
        env["LD_PRELOAD"] = str(PINNED_NCCL)
    env.update({
        "USE_TF": "0",
        "TRANSFORMERS_NO_TF": "1",
        "TRANSFORMERS_NO_TORCHVISION": "1",
        "VLLM_NO_USAGE_STATS": "1",
        "PYTORCH_ALLOC_CONF": "expandable_segments:True",
        "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
        # FlashInfer must target Blackwell explicitly in Kaggle's spawned vLLM
        # engine.  The attached offline CUDA 13.3 toolchain supplies a real
        # nvcc frontend; the vLLM/torch runtime remains the exact 0.27.1/cu129
        # champion runtime.
        "FLASHINFER_CUDA_ARCH_LIST": "12.0a",
        "TORCH_CUDA_ARCH_LIST": "12.0a",
        "CUDA_HOME": str(cuda_home),
        "CUDACXX": str(cuda_bin / "nvcc"),
        "PATH": f"{cuda_bin}{os.pathsep}{env.get('PATH', '')}",
        "LIBRARY_PATH": f"/usr/local/nvidia/lib64{os.pathsep}{env.get('LIBRARY_PATH', '')}",
    })
    return env


def install_runtime(wheelhouse: Path, compiler_wheelhouse: Path) -> None:
    lock = wheelhouse / "requirements.lock"
    if sha256(lock) != EXPECTED_LOCK_SHA256:
        raise RuntimeError(f"Wheelhouse lock drift: {sha256(lock)}")
    shutil.rmtree(SITE_PACKAGES, ignore_errors=True)
    SITE_PACKAGES.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, "-m", "pip", "install", "--no-index", "--find-links", str(wheelhouse),
        "--requirement", str(lock), "--target", str(SITE_PACKAGES), "--upgrade",
        "--ignore-installed", "--only-binary", ":all:", "--no-compile",
        "--disable-pip-version-check", "--no-warn-conflicts",
    ]
    subprocess.run(command, check=True)
    nccl_wheels = sorted(wheelhouse.glob("nvidia_nccl_cu12-2.29.7-*.whl"))
    if len(nccl_wheels) != 1:
        raise RuntimeError(f"Expected one pinned NCCL 2.29.7 wheel, got {nccl_wheels}")
    with zipfile.ZipFile(nccl_wheels[0]) as archive:
        nccl_members = [
            name for name in archive.namelist()
            if name.endswith("/libnccl.so.2") or "/libnccl.so.2." in name
        ]
        if not nccl_members:
            raise RuntimeError(f"Pinned NCCL wheel has no libnccl.so.2: {nccl_wheels[0]}")
        member = next(
            (name for name in nccl_members if name.endswith("/libnccl.so.2")),
            nccl_members[0],
        )
        NATIVE_LIB_DIR.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as source, PINNED_NCCL.open("wb") as target:
            shutil.copyfileobj(source, target)
    print(
        f"Pinned NCCL extracted: {PINNED_NCCL} sha256={sha256(PINNED_NCCL)}",
        flush=True,
    )
    compiler_links = compiler_wheelhouse / "wheels"
    subprocess.run([
        sys.executable, "-m", "pip", "install", "--no-index", "--find-links", str(compiler_links),
        "--target", str(SITE_PACKAGES), "--upgrade", "--ignore-installed", "--only-binary", ":all:",
        "--no-compile", "--disable-pip-version-check", "--no-warn-conflicts",
        "nvidia-cuda-nvcc==13.3.73", "nvidia-cuda-runtime==13.3.29",
        "nvidia-cuda-crt==13.3.73", "nvidia-nvvm==13.3.73",
        "nvidia-cuda-cccl==13.3.3.4.1", "nvidia-cuda-nvrtc==13.3.33",
        "nvidia-curand==10.4.3.29",
    ], check=True)
    runtime_wheels = sorted(compiler_links.glob("nvidia_cuda_runtime-13.3.29-*.whl"))
    if len(runtime_wheels) != 1:
        raise RuntimeError(f"Expected one pinned CUDA runtime 13.3.29 wheel, got {runtime_wheels}")
    cuda_lib64 = SITE_PACKAGES / "nvidia" / "cu13" / "lib64"
    cuda_lib64.mkdir(parents=True, exist_ok=True)
    pinned_cudart = cuda_lib64 / "libcudart.so.13"
    with zipfile.ZipFile(runtime_wheels[0]) as archive:
        cudart_members = [
            name for name in archive.namelist()
            if name.endswith("/libcudart.so.13") or "/libcudart.so.13." in name
        ]
        if not cudart_members:
            raise RuntimeError(f"Pinned CUDA runtime wheel has no libcudart.so.13: {runtime_wheels[0]}")
        member = next(
            (name for name in cudart_members if name.endswith("/libcudart.so.13")),
            cudart_members[0],
        )
        with archive.open(member) as source, pinned_cudart.open("wb") as target:
            shutil.copyfileobj(source, target)
    cudart_link = cuda_lib64 / "libcudart.so"
    cudart_link.unlink(missing_ok=True)
    cudart_link.symlink_to(pinned_cudart.name)
    print(
        f"Pinned CUDA runtime linked: {cudart_link} -> {pinned_cudart.name} "
        f"sha256={sha256(pinned_cudart)}",
        flush=True,
    )
    nvcc = SITE_PACKAGES / "nvidia" / "cu13" / "bin" / "nvcc"
    if not nvcc.is_file():
        raise FileNotFoundError(f"Offline CUDA compiler frontend missing: {nvcc}")
    nvcc.chmod(nvcc.stat().st_mode | 0o111)
    nvcc_check = subprocess.run(
        [str(nvcc), "--version"], env=serving_env(), check=True, capture_output=True, text=True,
    )
    print("Offline CUDA compiler:", nvcc_check.stdout.strip().splitlines()[-1], flush=True)
    print("Pinned NCCL preload:", serving_env().get("LD_PRELOAD", "missing"), flush=True)
    check = subprocess.run(
        [sys.executable, "-c", "import torch,vllm; print(torch.__version__,vllm.__version__)"],
        env=serving_env(), check=False, capture_output=True, text=True,
    )
    if check.stdout.strip():
        print("Runtime import stdout:", check.stdout.strip(), flush=True)
    if check.stderr.strip():
        print("Runtime import stderr:", check.stderr.strip(), flush=True)
    if check.returncode:
        raise RuntimeError(f"Isolated runtime import failed with exit {check.returncode}")
    versions = check.stdout.strip()
    print("Exact serving runtime:", versions, flush=True)
    if not versions.endswith("0.27.1"):
        raise RuntimeError(f"Expected vLLM 0.27.1, got {versions}")


def request_json(path: str, payload: dict | None = None, timeout: int = 30) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE_URL}{path}", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def tail(path: Path, lines: int = 100) -> str:
    if not path.is_file():
        return ""
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


def start_server(model_dir: Path) -> None:
    log_handle = SERVER_LOG.open("w", encoding="utf-8")
    command = [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", str(model_dir), "--served-model-name", SERVED_MODEL_NAME,
        "--host", "127.0.0.1", "--port", "1234", "--tensor-parallel-size", "1",
        "--enable-auto-tool-choice", "--tool-call-parser", "qwen3_coder",
        "--generation-config", "vllm", "--enable-prefix-caching",
        "--default-chat-template-kwargs", '{"preserve_thinking": true}',
        "--reasoning-parser", "qwen3", "--max-model-len", "65536",
        # The actual workload is 28 gameplay requests plus one curator.  Bound
        # graph capture to that real concurrency and reserve 15% of Kaggle's
        # 96 GB GPU for FP4 autotuning/graphs instead of exhausting it with the
        # generic 256-sequence capture plan.
        "--max-num-seqs", "32", "--gpu-memory-utilization", "0.85",
        "--enforce-eager",
    ]
    process = subprocess.Popen(
        command, env=serving_env(), stdout=log_handle, stderr=subprocess.STDOUT, text=True
    )
    SERVER_PID.write_text(str(process.pid), encoding="utf-8")
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"vLLM exited with {process.returncode}:\n{tail(SERVER_LOG)}")
        try:
            models = request_json("/models", timeout=5)
            print("NVFP4 server ready:", models, flush=True)
            break
        except Exception:
            time.sleep(5)
    else:
        raise TimeoutError(f"vLLM startup timed out:\n{tail(SERVER_LOG)}")
    smoke = request_json(
        "/chat/completions",
        {
            "model": SERVED_MODEL_NAME,
            "messages": [{"role": "user", "content": "Return exactly READY."}],
            "temperature": 0.0,
            "max_tokens": 128,
            "chat_template_kwargs": {"enable_thinking": False, "preserve_thinking": True},
        },
        timeout=180,
    )
    if not smoke.get("choices"):
        raise RuntimeError(f"NVFP4 smoke failed: {smoke}")
    (WORKING_DIR / "nvfp4-smoke.json").write_text(json.dumps(smoke, indent=2), encoding="utf-8")


def start_curator() -> None:
    CURATOR_DIR.mkdir(parents=True, exist_ok=True)
    ledger = CURATOR_DIR / "ledger.json"
    command = [
        sys.executable, str(BUNDLE_DIR / "nvfp4_cross_game_curator.py"),
        "--mode", "world_models", "--events-dir", str(WORKING_DIR),
        "--output-dir", str(CURATOR_DIR), "--base-url", BASE_URL,
        "--model", SERVED_MODEL_NAME, "--max-evidence", "10", "--min-games", "3",
        "--max-entries", "6", "--poll-seconds", "15", "--request-timeout", "900",
        "--max-tokens", "3600", "--temperature", "0.6", "--top-p", "0.95", "--top-k", "20",
    ]
    log_handle = CURATOR_LOG.open("w", encoding="utf-8")
    process = subprocess.Popen(command, stdout=log_handle, stderr=subprocess.STDOUT, text=True)
    CURATOR_PID.write_text(str(process.pid), encoding="utf-8")
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Curator exited with {process.returncode}:\n{tail(CURATOR_LOG)}")
        if ledger.is_file():
            data = json.loads(ledger.read_text(encoding="utf-8"))
            if data.get("influence_mode") == "nvfp4_persistent_world_models_to_gameplay":
                print("Persistent world-model curator ready:", ledger, flush=True)
                return
        time.sleep(2)
    raise TimeoutError(f"Curator did not initialize its ledger:\n{tail(CURATOR_LOG)}")


wheelhouse = resolve_wheelhouse()
compiler_wheelhouse = resolve_cuda_compiler_wheelhouse()
model_dir = resolve_model()
print("Exact wheelhouse:", wheelhouse, flush=True)
print("CUDA compiler wheelhouse:", compiler_wheelhouse, flush=True)
print("Exact NVFP4 model:", model_dir, flush=True)
install_runtime(wheelhouse, compiler_wheelhouse)
start_server(model_dir)
start_curator()

setup_env_path = Path(os.environ["TAAF_KAGGLE_SETUP_ENV"])
persisted = json.loads(setup_env_path.read_text(encoding="utf-8"))
persisted.update({
    "PYTHONPATH": serving_env()["PYTHONPATH"],
    "USE_TF": "0",
    "TRANSFORMERS_NO_TF": "1",
    "TRANSFORMERS_NO_TORCHVISION": "1",
    "VLLM_NO_USAGE_STATS": "1",
    "LOCAL_ANALYZER_BASE_URL": BASE_URL,
    "OPENAI_BASE_URL": BASE_URL,
    "LOCAL_ANALYZER_PROVIDER": "vllm",
    "OPENAI_PROVIDER": "vllm",
    "LOCAL_ANALYZER_MODEL_ID": SERVED_MODEL_NAME,
    "INFERENCE_ANALYZER_MODEL": SERVED_MODEL_NAME,
    "LOCAL_ANALYZER_APP_NAME": "ARC3 Agent Harness",
    "LOCAL_ANALYZER_CONTEXT_WINDOW": "32768",
    "LOCAL_ANALYZER_MAX_OUTPUT": "0",
    "LOCAL_ANALYZER_TOOL_STEPS": "0",
    "LOCAL_ANALYZER_TOOL_TIMEOUT": "30",
    "LOCAL_ANALYZER_TOOL_OUTPUT_TOKENS": "1024",
    "LOCAL_ANALYZER_YIELD_SECONDS": "60",
    "LOCAL_ANALYZER_TEMPERATURE": "1.0",
    "LOCAL_ANALYZER_TOP_P": "0.95",
    "LOCAL_ANALYZER_TOP_K": "20",
    "LOCAL_ANALYZER_ENABLE_THINKING": "true",
    "MULTIMODAL_CONTEXT": "current_grid",
    "MULTIMODAL_UPSCALE": "4",
    "ARC3_COMMON_THEMES_PATH": str(CURATOR_DIR / "ledger.json"),
    "ARC3_COMMON_THEMES_INJECTION_LOG": str(CURATOR_DIR / "gameplay-world-model-injections.jsonl"),
    "ARC3_COMMON_THEMES_MAX": "12",
    "ARC3_COMMON_THEMES_MAX_CHARS": "6000",
})
setup_env_path.write_text(json.dumps(persisted, indent=2, sort_keys=True) + "\n", encoding="utf-8")
'''


TEARDOWN_SCRIPT = r'''from __future__ import annotations

import os
import shutil
import signal
import time
from pathlib import Path

working = Path(os.environ["TAAF_KAGGLE_WORKING_DIR"])
for pid_path in [working / "world-model-curator" / "curator.pid", working / "vllm-openai-server.pid"]:
    if not pid_path.is_file():
        continue
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                break
            time.sleep(1)
        else:
            os.kill(pid, signal.SIGKILL)
    except Exception as exc:
        print(f"Could not stop {pid_path}: {exc!r}", flush=True)
    pid_path.unlink(missing_ok=True)
shutil.rmtree(working / "vllm-site-packages", ignore_errors=True)
print("Stopped curator and vLLM; removed temporary serving runtime", flush=True)
'''


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_hash(path: Path, expected: str, label: str) -> None:
    actual = sha256(path)
    if actual != expected:
        raise RuntimeError(f"{label} SHA-256 drift: {actual} != {expected}")


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_dataset() -> None:
    if OUT_DATASET.exists():
        raise FileExistsError(f"Refusing to overwrite {OUT_DATASET}")
    shutil.copytree(SOURCE_BUNDLE, OUT_DATASET)
    shutil.make_archive(str(OUT_DATASET / "src"), "zip", root_dir=OUT_DATASET / "src")
    shutil.copy2(SOURCE_CURATOR, OUT_DATASET / "nvfp4_cross_game_curator.py")
    # The canonical setup is separately syntax/audit checked and deliberately
    # reproduces the successful GCP cu130 closure.  Do not regenerate the old
    # hybrid cu129/cu133 setup embedded above.
    shutil.copy2(CANONICAL_SETUP, OUT_DATASET / "kaggle_nvfp4_world_model_setup.py")
    shutil.copytree(EXACT_MODEL_ASSETS, OUT_DATASET / "exact-gcp-model-assets")
    shutil.copytree(EXACT_ENGINE_WHEELS, OUT_DATASET / "engine-wheels")
    (OUT_DATASET / "kaggle_nvfp4_world_model_teardown.py").write_text(TEARDOWN_SCRIPT, encoding="utf-8")
    write_json(
        OUT_DATASET / "setup_commands.json",
        ['"$PYTHON" "$TAAF_KAGGLE_BUNDLE_DIR/kaggle_nvfp4_world_model_setup.py"'],
    )
    write_json(
        OUT_DATASET / "teardown_commands.json",
        ['"$PYTHON" "$TAAF_KAGGLE_BUNDLE_DIR/kaggle_nvfp4_world_model_teardown.py"'],
    )
    write_json(
        OUT_DATASET / "dataset-metadata.json",
        {"title": "TAAF Qwen3.8 NVFP4 world-model curator", "id": DATASET_REF,
         "licenses": [{"name": "MIT"}]},
    )
    write_json(
        OUT_DATASET / "NVFP4_WORLD_MODEL_KAGGLE_MANIFEST.json",
        {
            "schema_version": 1,
            "candidate": "Qwen3.8 NVFP4 compact-English checkpoint-8 general-thinking plus persistent world-model curator",
            "model": MODEL_ID,
            "model_revision": MODEL_REVISION,
            "vllm": "0.27.1",
            "mtp_enabled": False,
            "gameplay_sampling": {"temperature": 1.0, "top_p": 0.95, "top_k": 20},
            "curator_sampling": {"temperature": 0.6, "top_p": 0.95, "top_k": 20},
            "checkpoint_limit": 8,
            "concurrency": 28,
            "current_grid_scale": 4,
            "max_runtime_s_per_game": 7920,
            "request_logs_required": True,
            "curator": {"mode": "world_models", "max_evidence": 10, "min_games": 3,
                        "max_entries": 6, "poll_seconds": 15, "max_tokens": 3600},
            "gcp_replicas": [
                {"run": "g4run-q38-cap8-ce-think-nvfp4-wmgpu-r6-20260821-014307", "mean25": 7.9424},
                {"run": "g4run-q38-cap8-ce-think-nvfp4-wmgpu-p2r2-20260821-123422", "mean25": 6.4529},
            ],
            "gcp_pair_mean25": 7.1976,
            "source_sha256": EXPECTED,
            "wheelhouse": WHEELHOUSE_REF,
            "model_source": MODEL_REF,
            "effective_model_package": "first-party byte-exact GCP NVFP4 package with verified legacy-overlay fallback",
        },
    )


def cell_text(cell: dict[str, object]) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else str(source)


def build_kernel() -> None:
    if OUT_KERNEL.exists():
        raise FileExistsError(f"Refusing to overwrite {OUT_KERNEL}")
    OUT_KERNEL.mkdir(parents=True)
    notebook = json.loads(SOURCE_NOTEBOOK.read_text(encoding="utf-8"))
    notebook["cells"][0]["source"] = (
        "# ARC3 Qwen3.8 NVFP4 + persistent world-model curator\n\n"
        "Replicated GCP champion: compact-English checkpoint-8 general-thinking, with one asynchronous "
        "cross-game curator sharing the exact NVFP4 server.\n"
    )
    notebook["cells"][6]["source"] = cell_text(notebook["cells"][6]).replace(
        'DATASET_SOURCES = ["sonphamorg/taaf-source-native-cap8-qwen38-simplified-english", "driessmit1/arc3-vllm-h100-wheelhouse-v3", "saltb0x/qwen3-8-27b-fp8"]',
        f'DATASET_SOURCES = ["{DATASET_REF}", "{WHEELHOUSE_REF}"]',
    )
    notebook["cells"][2]["source"] = cell_text(notebook["cells"][2]).replace(
        "import time\n",
        "import time\nimport zipfile\n",
    )
    notebook["cells"][4]["source"] = cell_text(notebook["cells"][4]).replace(
        '        "arc-agi",',
        '        "arc-agi==0.9.8",',
    )
    notebook["cells"][8]["source"] = cell_text(notebook["cells"][8]).replace(
        '''def _source_path_entries(bundle_dir: Path) -> list:
    entries = []
    for repo in sorted((bundle_dir / "src").iterdir(), reverse=True):''',
        '''def _source_path_entries(bundle_dir: Path) -> list:
    source_root = bundle_dir / "src"
    if not source_root.is_dir():
        source_archive = bundle_dir / "src.zip"
        if not source_archive.is_file():
            raise RuntimeError(f"TAAF bundle has neither src/ nor src.zip: {bundle_dir}")
        source_root = WORKING_DIR / "taaf-bundle-src"
        if not source_root.is_dir():
            source_root.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(source_archive) as archive:
                archive.extractall(source_root)
        print(f"taaf.kaggle: materialized bundle sources at {source_root}")
    entries = []
    for repo in sorted(source_root.iterdir(), reverse=True):''',
    )
    notebook["cells"][9]["source"] = "## 5. Champion general-thinking sampling\n"
    notebook["cells"][10]["source"] = cell_text(notebook["cells"][10]).replace(
        "# Sampling-profile sweep winner: change only analyzer sampling before the benchmark is unpickled.",
        "# Replicated champion sampling; the setup already started the exact NVFP4 server and curator.",
    )
    notebook["cells"][14]["source"] = '''# Exact replicated NVFP4 world-model-curator configuration.
bm.solver.max_runtime_s_per_game = 7920.0
bm.solver.concurrency = 28
bm.solver.save_request_logs = True
assert bm.solver.max_runtime_s_per_game == 7920.0
assert bm.solver.concurrency == 28
assert bm.solver.save_request_logs is True
print("Kaggle parity: checkpoint-8, concurrency28, request logs enabled for persistent curator")
'''
    for cell in notebook["cells"]:
        cell.pop("id", None)
        if cell.get("cell_type") == "code":
            cell["outputs"] = []
            cell["execution_count"] = None
    OUT_NOTEBOOK.write_text(json.dumps(notebook, indent=1) + "\n", encoding="utf-8")
    metadata = json.loads((SOURCE_KERNEL / "kernel-metadata.json").read_text(encoding="utf-8"))
    metadata.update({
        "id": KERNEL_ID,
        "title": "ARC3 Qwen3.8 NVFP4 world-model curator",
        "code_file": OUT_NOTEBOOK.name,
        "is_private": True,
        "dataset_sources": [DATASET_REF, WHEELHOUSE_REF],
        "model_sources": [MODEL_REF],
    })
    metadata.pop("id_no", None)
    write_json(OUT_KERNEL / "kernel-metadata.json", metadata)


def validate() -> None:
    require_hash(
        SOURCE_BUNDLE / "src" / "ARC3-Inference" / "inference" / "agent" / "tool_agent.py",
        EXPECTED["bundle_tool_agent"], "tool_agent",
    )
    require_hash(
        SOURCE_BUNDLE / "src" / "ARC3-Inference" / "inference" / "framework" / "solver.py",
        EXPECTED["bundle_solver"], "solver",
    )
    require_hash(SOURCE_CURATOR, EXPECTED["curator"], "curator")
    canonical_setup = CANONICAL_SETUP.read_text(encoding="utf-8")
    if EXPECTED["wheelhouse_lock"] not in canonical_setup:
        raise RuntimeError("Canonical exact-GCP wheelhouse lock marker is missing")
    if '"--linear-backend", "cutlass"' in canonical_setup:
        raise RuntimeError("Canonical Kaggle setup still forces the non-champion cutlass backend")
    for wheel in ("arc_agi-0.9.8-py3-none-any.whl", "arcengine-0.9.3-py3-none-any.whl"):
        if not (EXACT_ENGINE_WHEELS / wheel).is_file():
            raise RuntimeError(f"Exact champion engine wheel is missing: {wheel}")
    for name, expected in EXPECTED_MODEL_ASSETS.items():
        require_hash(EXACT_MODEL_ASSETS / name, expected, f"exact GCP model asset {name}")
    required_setup_markers = [
        "effective_package_byte_exact", "nvfp4-package-behavior-audit.json",
        "model_mtp.safetensors", "EXACT_MODEL_ASSETS", "owned_model_direct", MODEL_REF,
    ]
    missing_setup_markers = [marker for marker in required_setup_markers if marker not in canonical_setup]
    if missing_setup_markers:
        raise RuntimeError(f"Canonical exact-model overlay markers missing: {missing_setup_markers}")
    rendered = OUT_NOTEBOOK.read_text(encoding="utf-8")
    required = [DATASET_REF, WHEELHOUSE_REF, "arc-agi==0.9.8", "bm.solver.save_request_logs = True",
                "bm.solver.concurrency = 28", "bm.solver.max_runtime_s_per_game = 7920.0"]
    missing = [marker for marker in required if marker not in rendered]
    if missing:
        raise RuntimeError(f"Notebook parity markers missing: {missing}")
    if "saltb0x/qwen3-8-27b-fp8" in rendered or "driessmit1/arc3-vllm-h100-wheelhouse-v3" in rendered:
        raise RuntimeError("Notebook retained an obsolete FP8 input")
    metadata = json.loads((OUT_KERNEL / "kernel-metadata.json").read_text(encoding="utf-8"))
    if metadata["model_sources"] != [MODEL_REF]:
        raise RuntimeError("Exact NVFP4 Kaggle model is not the sole model source")
    print(json.dumps({
        "dataset": str(OUT_DATASET), "kernel": str(OUT_KERNEL),
        "dataset_files": sum(path.is_file() for path in OUT_DATASET.rglob("*")),
        "notebook_sha256": sha256(OUT_NOTEBOOK),
        "kernel_metadata_sha256": sha256(OUT_KERNEL / "kernel-metadata.json"),
    }, indent=2))


def main() -> None:
    STAGE.mkdir(parents=True, exist_ok=True)
    build_dataset()
    build_kernel()
    validate()


if __name__ == "__main__":
    main()
