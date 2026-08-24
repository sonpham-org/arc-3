from __future__ import annotations

import hashlib
import ctypes
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path

WHEELHOUSE_REF = "sonphamorg/arc3-vllm-wheelhouse-v0271-gcp-cu130-exact"
MODEL_REF = "sonphamorg/qwen3-8-27b-nvfp4-gcp-exact/PyTorch/gcp-exact/1"
SERVED_MODEL_NAME = "unsloth/Qwen3.8-27B-NVFP4"
EXPECTED_MODEL_REVISION = "7d6f8d4d72f56b92b3cdbf22f156b90e1bab0108"
EXPECTED_LOCK_SHA256 = "b3d4e737a311ac3f19525ee5ea3afe6d6c773c76bf6c34fb5a0b2ac4c15fca56"
EXPECTED_MANIFEST_SHA256 = "d2ea0b109ca22f697b46deeb934716b8bec2b566b7ffe5d5ed8f441b64715ae1"
WHEELHOUSE_ARCHIVE = "arc3-vllm-wheelhouse-v0271-gcp-cu130-exact.tar"
EXPECTED_ARCHIVE_SHA256 = "cb9fc705b256d598bd7331415094cf75bbb63414ef0c48a30fb8c9e8b394bc39"
EXPECTED_ARC_RUNTIME_WHEELS = {
    "arc_agi-0.9.8-py3-none-any.whl": {
        "bytes": 40151,
        "sha256": "aeca1663db342e91cb8fc96cf0c83e2fa39db1640bc1298e80a8d522e3af70f3",
    },
    "arcengine-0.9.3-py3-none-any.whl": {
        "bytes": 38374,
        "sha256": "5f9739d6d0055780a4581fd6fe09066bb08775c4c8212c9adcca2eb008aef59c",
    },
}
EXPECTED_MODEL_ARTIFACTS = {
    ".gitattributes": "34448b82c17d60fec9b65b1f093c115ddbaadc04beb1b0140b6bfed2e012a930",
    "README.md": "990276a7c285e41dff56d2a50d2ebf29c0b66b6bf030c922506196dc5484efe5",
    "chat_template.jinja": "12827f24b742ea4e80cdc12dbcf9622227056b9f797252a3149263d4f9aaadce",
    "config.json": "1b3c71868d1299e52df6fc907deb202d5132b1ef0f72aae0ef6d15185dd53a5c",
    "generation_config.json": "d0d0ed2e37cdfafef4a5067d5ea2407b05f4fb50526e47c008a5b235d50240fb",
    "model.safetensors": "c473512c70eace07e2256fe9fd76596ac03e3295bee7d54cfb72676416afcc05",
    "model.safetensors.index.json": "429430e1b9e65b2cb98eff8cd10a06e70a09cee89c48487a3914684aeb6df57f",
    "model_mtp.safetensors": "1d8268aa85ace093a561e3e7b63b9d390dac1cd55a90cd55b5ec509c3c9da9fe",
    "preprocessor_config.json": "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516",
    "tokenizer.json": "06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523",
    "tokenizer_config.json": "529f30018c36dca5387c99b5edf368287f386f2c32d3790aa7141956bc5119fa",
    "video_preprocessor_config.json": "7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13",
    "vocab.json": "ce99b4cb2983d118806ce0a8b777a35b093e2000a503ebde25853284c9dfa003",
}
MODEL_WEIGHT_ARTIFACTS = {"model.safetensors", "model_mtp.safetensors"}
CUDA130_COMPILER_WHEELS = {
    "nvidia_cuda_nvcc-13.0.88-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl": {
        "bytes": 37384532,
        "sha256": "56fe502eb77625a12f25172caa3cdddb4e4c8ba2c8c17dba44b164761b380f03",
    },
    "nvidia_cuda_crt-13.0.88-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl": {
        "bytes": 134086,
        "sha256": "2c8043c7c9e02492716426e9919fc78d2c5b3b2a7a768a88e952676b08aa55a4",
    },
    "nvidia_nvvm-13.0.88-py3-none-manylinux2010_x86_64.manylinux_2_12_x86_64.whl": {
        "bytes": 61601415,
        "sha256": "c5f41ffeb6466944a026dfa5317d7d85355c119bbec279205d22f1869d1054e0",
    },
}
WORKING_DIR = Path(os.environ["TAAF_KAGGLE_WORKING_DIR"])
BUNDLE_DIR = Path(os.environ["TAAF_KAGGLE_BUNDLE_DIR"])
EXACT_MODEL_ASSETS = BUNDLE_DIR / "exact-gcp-model-assets"
EXACT_MODEL_ASSETS_ARCHIVE = BUNDLE_DIR / "exact-gcp-model-assets.zip"
EFFECTIVE_MODEL_DIR = WORKING_DIR / "exact-gcp-nvfp4-model"
SITE_PACKAGES = WORKING_DIR / "vllm-site-packages"
SERVER_LOG = WORKING_DIR / "vllm-openai-server.log"
SERVER_PID = WORKING_DIR / "vllm-openai-server.pid"
CURATOR_DIR = WORKING_DIR / "world-model-curator"
CURATOR_LOG = CURATOR_DIR / "curator.log"
CURATOR_PID = CURATOR_DIR / "curator.pid"
BASE_URL = "http://127.0.0.1:1234/v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_text_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def install_exact_arc_runtime() -> None:
    """Replace Kaggle's generic competition install with the GCP engine wheels."""
    wheel_dir = BUNDLE_DIR / "engine-wheels"
    wheel_paths: list[Path] = []
    for filename, expected in EXPECTED_ARC_RUNTIME_WHEELS.items():
        wheel = wheel_dir / filename
        if not wheel.is_file() or wheel.stat().st_size != int(expected["bytes"]):
            raise RuntimeError(f"Exact ARC runtime wheel missing or size-drifted: {wheel}")
        actual = sha256(wheel)
        if actual != expected["sha256"]:
            raise RuntimeError(f"Exact ARC runtime wheel SHA-256 drift: {wheel} = {actual}")
        wheel_paths.append(wheel)
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install", "--no-index", "--no-deps",
            "--force-reinstall", "--disable-pip-version-check", "--no-warn-conflicts",
            *(str(path) for path in wheel_paths),
        ],
        check=True,
    )
    check = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from importlib.metadata import version; "
                "print(version('arc-agi'), version('arcengine'))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    if check.stdout.strip() != "0.9.8 0.9.3":
        raise RuntimeError(f"Exact ARC runtime version drift: {check.stdout.strip()}")
    (WORKING_DIR / "arc-runtime-provenance.json").write_text(
        json.dumps(
            {
                "arc-agi": EXPECTED_ARC_RUNTIME_WHEELS["arc_agi-0.9.8-py3-none-any.whl"],
                "arcengine": EXPECTED_ARC_RUNTIME_WHEELS["arcengine-0.9.3-py3-none-any.whl"],
                "versions": check.stdout.strip().split(),
                "source": "bundled champion GCP engine wheels",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print("Exact ARC runtime: arc-agi 0.9.8, arcengine 0.9.3", flush=True)


def input_paths() -> dict[str, Path]:
    raw = json.loads(os.environ.get("TAAF_KAGGLE_INPUT_PATHS", "{}"))
    return {str(key): Path(str(value)) for key, value in raw.items()}


def resolve_wheelhouse() -> Path:
    mapped = input_paths().get(WHEELHOUSE_REF)
    candidates = [
        mapped,
        Path("/kaggle/input/arc3-vllm-wheelhouse-v0271-gcp-cu130-exact"),
        Path("/kaggle/input/datasets/sonphamorg/arc3-vllm-wheelhouse-v0271-gcp-cu130-exact"),
    ]
    for candidate in candidates:
        if candidate and (candidate / "requirements.lock").is_file():
            return candidate
        archive = candidate / WHEELHOUSE_ARCHIVE if candidate else None
        if archive and archive.is_file():
            actual = sha256(archive)
            if actual != EXPECTED_ARCHIVE_SHA256:
                raise RuntimeError(f"Exact wheelhouse archive drift: {actual}")
            materialized = WORKING_DIR / "exact-gcp-cu130-wheelhouse"
            if not (materialized / "requirements.lock").is_file():
                shutil.rmtree(materialized, ignore_errors=True)
                materialized.mkdir(parents=True)
                with tarfile.open(archive, "r:") as payload:
                    payload.extractall(materialized, filter="data")
            if sha256(materialized / "requirements.lock") != EXPECTED_LOCK_SHA256:
                raise RuntimeError("Materialized wheelhouse lock drift")
            print(f"Materialized exact GCP wheelhouse from {archive}", flush=True)
            return materialized
    raise FileNotFoundError(f"Exact vLLM wheelhouse is not mounted: {candidates}")


def resolve_exact_model_assets() -> Path:
    if EXACT_MODEL_ASSETS.is_dir():
        return EXACT_MODEL_ASSETS
    if not EXACT_MODEL_ASSETS_ARCHIVE.is_file():
        raise FileNotFoundError(
            f"Pinned GCP model assets are missing: {EXACT_MODEL_ASSETS} / {EXACT_MODEL_ASSETS_ARCHIVE}"
        )
    materialized = WORKING_DIR / "exact-gcp-model-assets"
    shutil.rmtree(materialized, ignore_errors=True)
    materialized.mkdir(parents=True)
    with zipfile.ZipFile(EXACT_MODEL_ASSETS_ARCHIVE) as archive:
        archive.extractall(materialized)
    print(f"Materialized exact GCP model assets from {EXACT_MODEL_ASSETS_ARCHIVE}", flush=True)
    return materialized


def resolve_model() -> tuple[Path, Path]:
    # Kaggle's model mount prefix is not stable across imported and first-party
    # model variations.  Discover the immutable 22.6 GB weight object exactly
    # as the successful owned-package verifier does, instead of assuming a
    # particular /kaggle/input/models/... prefix.
    configs: list[Path] = []
    for model_file in Path("/kaggle/input").rglob("model.safetensors"):
        if model_file.stat().st_size > 20_000_000_000:
            config_path = model_file.parent / "config.json"
            if config_path.is_file():
                configs.append(config_path)
    valid_by_path: dict[str, Path] = {}
    for config_path in configs:
        model_dir = config_path.parent
        model_file = model_dir / "model.safetensors"
        if model_file.is_file() and model_file.stat().st_size > 20_000_000_000:
            valid_by_path[str(model_dir.resolve())] = model_dir
    valid = list(valid_by_path.values())
    if len(valid) != 1:
        raise RuntimeError(f"Expected exactly one attached NVFP4 model directory, got {valid}")
    model_dir = valid[0]
    config = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
    quant = config.get("quantization_config") or {}
    quant_text = json.dumps(quant, sort_keys=True).lower()
    if "nvfp4" not in quant_text or "compressed" not in quant_text:
        raise RuntimeError(f"Attached model is not compressed-tensors NVFP4: {quant}")

    # Our first-party Kaggle variation contains the complete pinned package.
    # If every artifact is already byte-exact, serve it directly: no overlay,
    # no dependency on Kaggle's Hugging Face import behavior, and no chance for
    # config/tokenizer drift between model revisions.
    raw_artifacts: dict[str, str] = {}
    for name in EXPECTED_MODEL_ARTIFACTS:
        path = model_dir / name
        raw_artifacts[name] = sha256(path) if path.is_file() else "missing"
    if all(
        raw_artifacts.get(name) == expected
        for name, expected in EXPECTED_MODEL_ARTIFACTS.items()
    ):
        provenance = {
            "upstream_revision": EXPECTED_MODEL_REVISION,
            "kaggle_model_ref": MODEL_REF,
            "kaggle_import_ref": "first-party-upload",
            "weight_sha256_verified": raw_artifacts["model.safetensors"],
            "kaggle_import_artifacts": raw_artifacts,
            "kaggle_import_drift": [],
            "effective_model_dir": str(model_dir),
            "effective_artifacts": raw_artifacts,
            "effective_package_byte_exact": True,
            "owned_model_direct": True,
        }
        (WORKING_DIR / "nvfp4-model-provenance.json").write_text(
            json.dumps(provenance, indent=2), encoding="utf-8"
        )
        print(
            f"First-party Kaggle NVFP4 package is byte-exact; serving directly from {model_dir}",
            flush=True,
        )
        return model_dir, model_dir

    # Kaggle's model import is useful for mounting the large immutable weight
    # objects, but it is not the effective serving package: Kaggle rewrites some
    # auxiliary assets.  Audit the import, then build a writable overlay whose
    # config/tokenizer files are byte-exact copies of the pinned GCP snapshot.
    observed_artifacts: dict[str, str] = {}
    for name, expected in EXPECTED_MODEL_ARTIFACTS.items():
        path = model_dir / name
        if not path.is_file() and name not in MODEL_WEIGHT_ARTIFACTS:
            observed_artifacts[name] = "missing"
            print(f"Kaggle-import auxiliary artifact missing: {name}", flush=True)
            continue
        if not path.is_file():
            raise FileNotFoundError(path)
        if name in MODEL_WEIGHT_ARTIFACTS:
            actual = raw_artifacts[name]
        else:
            actual = normalized_text_sha256(path)
        observed_artifacts[name] = actual
        if name in MODEL_WEIGHT_ARTIFACTS and actual != expected:
            raise RuntimeError(f"NVFP4 artifact drift for {name}: {actual} != {expected}")
        if name not in MODEL_WEIGHT_ARTIFACTS and actual != expected:
            print(f"Kaggle-import auxiliary artifact differs for {name}: {actual}", flush=True)

    exact_model_assets = resolve_exact_model_assets()
    shutil.rmtree(EFFECTIVE_MODEL_DIR, ignore_errors=True)
    EFFECTIVE_MODEL_DIR.mkdir(parents=True)
    effective_artifacts: dict[str, str] = {}
    for name, expected in EXPECTED_MODEL_ARTIFACTS.items():
        destination = EFFECTIVE_MODEL_DIR / name
        if name in MODEL_WEIGHT_ARTIFACTS:
            source = model_dir / name
            os.symlink(source, destination)
            if not os.path.samefile(source, destination):
                raise RuntimeError(f"Effective weight link does not resolve to imported artifact: {name}")
            effective_artifacts[name] = observed_artifacts[name]
        else:
            source = exact_model_assets / name
            if not source.is_file():
                raise FileNotFoundError(source)
            actual = sha256(source)
            if actual != expected:
                raise RuntimeError(f"Pinned GCP model asset drift for {name}: {actual} != {expected}")
            shutil.copy2(source, destination)
            effective_artifacts[name] = sha256(destination)
        if effective_artifacts[name] != expected:
            raise RuntimeError(
                f"Effective GCP model package drift for {name}: "
                f"{effective_artifacts[name]} != {expected}"
            )

    ref_path = model_dir / ".git" / "refs" / "heads" / "main"
    imported_ref = ref_path.read_text(encoding="utf-8").strip() if ref_path.is_file() else "unknown"
    imported_drift = sorted(
        name for name, expected in EXPECTED_MODEL_ARTIFACTS.items()
        if observed_artifacts.get(name) != expected
    )
    (WORKING_DIR / "nvfp4-model-provenance.json").write_text(
        json.dumps({
            "upstream_revision": EXPECTED_MODEL_REVISION,
            "kaggle_import_ref": imported_ref,
            "weight_sha256_verified": observed_artifacts["model.safetensors"],
            "kaggle_import_artifacts": observed_artifacts,
            "kaggle_import_drift": imported_drift,
            "effective_model_dir": str(EFFECTIVE_MODEL_DIR),
            "effective_artifacts": effective_artifacts,
            "effective_package_byte_exact": True,
        }, indent=2),
        encoding="utf-8",
    )
    print(
        f"Exact GCP NVFP4 serving overlay verified; import ref={imported_ref}; "
        f"replaced auxiliary drift={imported_drift}",
        flush=True,
    )
    return model_dir, EFFECTIVE_MODEL_DIR


def serving_env() -> dict[str, str]:
    env = os.environ.copy()
    current = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SITE_PACKAGES) if not current else f"{SITE_PACKAGES}{os.pathsep}{current}"
    cuda_home = SITE_PACKAGES / "nvidia" / "cu13"
    cuda_bin = cuda_home / "bin"
    cuda_lib = cuda_home / "lib"
    current_path = env.get("PATH", "")
    current_ld_library_path = env.get("LD_LIBRARY_PATH", "")
    env["CUDA_HOME"] = str(cuda_home)
    env["CUDA_PATH"] = str(cuda_home)
    env["PATH"] = str(cuda_bin) if not current_path else f"{cuda_bin}{os.pathsep}{current_path}"
    env["LD_LIBRARY_PATH"] = (
        str(cuda_lib)
        if not current_ld_library_path
        else f"{cuda_lib}{os.pathsep}{current_ld_library_path}"
    )
    # Kaggle is offline and FlashInfer cannot infer the Blackwell target from
    # its remote prebuilt-kernel registry.  The exact wheelhouse ships CUDA
    # 13.3 nvcc, so pin the observed RTX Pro 6000 capability explicitly.
    env["FLASHINFER_CUDA_ARCH_LIST"] = "12.0f"
    env.update({
        "USE_TF": "0",
        "TRANSFORMERS_NO_TF": "1",
        "TRANSFORMERS_NO_TORCHVISION": "1",
        "VLLM_NO_USAGE_STATS": "1",
    })
    return env


def materialize_wheel_name_links(wheelhouse: Path, wheels: list[dict]) -> Path:
    """Restore wheel names that Kaggle truncates at its 128-character file limit."""
    missing = [item for item in wheels if not (wheelhouse / item["file"]).is_file()]
    if not missing:
        return wheelhouse

    link_root = WORKING_DIR / "exact-gcp-cu130-wheel-links"
    shutil.rmtree(link_root, ignore_errors=True)
    link_root.mkdir(parents=True)
    observed = [path for path in wheelhouse.iterdir() if path.is_file()]
    repaired: list[dict[str, str]] = []

    for item in wheels:
        expected_name = item["file"]
        source = wheelhouse / expected_name
        if not source.is_file():
            matches = [
                path
                for path in observed
                if expected_name.startswith(path.name)
                and path.stat().st_size == int(item["bytes"])
            ]
            if len(matches) != 1:
                raise RuntimeError(
                    f"Could not uniquely repair Kaggle-truncated wheel {expected_name}: {matches}"
                )
            source = matches[0]
            repaired.append({"expected": expected_name, "mounted_as": source.name})
        os.symlink(source, link_root / expected_name)

    os.symlink(wheelhouse / "requirements.lock", link_root / "requirements.lock")
    os.symlink(
        wheelhouse / "WHEELHOUSE_MANIFEST.json",
        link_root / "WHEELHOUSE_MANIFEST.json",
    )
    print(f"Repaired Kaggle-truncated wheel names: {json.dumps(repaired)}", flush=True)
    return link_root


def install_runtime(wheelhouse: Path) -> None:
    lock = wheelhouse / "requirements.lock"
    if sha256(lock) != EXPECTED_LOCK_SHA256:
        raise RuntimeError(f"Wheelhouse lock drift: {sha256(lock)}")
    manifest_path = wheelhouse / "WHEELHOUSE_MANIFEST.json"
    if sha256(manifest_path) != EXPECTED_MANIFEST_SHA256:
        raise RuntimeError(f"Wheelhouse manifest drift: {sha256(manifest_path)}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    wheels = manifest.get("wheels") or []
    if manifest.get("package_count") != 195 or len(wheels) != 195:
        raise RuntimeError("Exact GCP wheelhouse does not contain 195 manifest entries")
    wheelhouse = materialize_wheel_name_links(wheelhouse, wheels)
    for item in wheels:
        wheel = wheelhouse / item["file"]
        if not wheel.is_file() or wheel.stat().st_size != int(item["bytes"]):
            raise RuntimeError(f"Wheel missing or size-drifted: {wheel}")
        actual = sha256(wheel)
        if actual != item["sha256"]:
            raise RuntimeError(f"Wheel SHA-256 drift for {wheel.name}: {actual}")
    print("Verified all 195 exact GCP runtime wheels byte-for-byte", flush=True)
    shutil.rmtree(SITE_PACKAGES, ignore_errors=True)
    SITE_PACKAGES.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, "-m", "pip", "install", "--no-index", "--find-links", str(wheelhouse),
        "--requirement", str(lock), "--target", str(SITE_PACKAGES), "--upgrade",
        "--ignore-installed", "--only-binary", ":all:", "--no-compile",
        "--disable-pip-version-check", "--no-warn-conflicts",
    ]
    subprocess.run(command, check=True)
    check = subprocess.run(
        [sys.executable, "-c", (
            "import platform,torch,transformers,vllm; "
            "print(platform.python_version(),torch.__version__,torch.version.cuda,"
            "transformers.__version__,vllm.__version__)"
        )],
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
    fields = versions.split()
    if len(fields) != 5 or fields[1] != "2.13.0+cu130" or fields[2] != "13.0" or fields[3:] != ["5.15.1", "0.27.1"]:
        raise RuntimeError(f"Expected Python3.12 / torch2.13.0+cu130 / CUDA13.0 / transformers5.15.1 / vLLM0.27.1, got {versions}")


def resolve_cuda130_compiler_dir() -> Path:
    """Return the pinned compiler payload from either Kaggle mount layout."""
    compiler_dir = BUNDLE_DIR / "cuda130-sm120-compiler"
    if compiler_dir.is_dir():
        return compiler_dir

    archive = BUNDLE_DIR / "cuda130-sm120-compiler.zip"
    if not archive.is_file():
        raise FileNotFoundError(
            "Missing pinned CUDA 13.0 compiler payload: expected "
            f"{compiler_dir} or {archive}"
        )

    materialized = WORKING_DIR / "cuda130-sm120-compiler"
    shutil.rmtree(materialized, ignore_errors=True)
    materialized.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as payload:
        payload.extractall(materialized)
    print(f"Materialized pinned CUDA compiler archive: {archive}", flush=True)
    return materialized


def overlay_matching_cuda130_compiler() -> None:
    """Replace only mismatched 13.3 JIT components with CUDA 13.0.88.

    The exact GCP wheel lock resolves torch's CUDA 13.0 runtime headers but a
    newer CUDA 13.3 compiler package.  GCP did not need offline sampler JIT;
    Kaggle does, and CUDA correctly rejects compiler/header minor-version
    drift.  These three pinned wheels restore coherent nvcc/CRT/ptxas plus
    NVVM/cicc/libdevice at CUDA 13.0.88 without changing torch, vLLM,
    FlashInfer, or gameplay.
    """
    compiler_dir = resolve_cuda130_compiler_dir()
    for filename, expected in CUDA130_COMPILER_WHEELS.items():
        wheel = compiler_dir / filename
        if not wheel.is_file() or wheel.stat().st_size != expected["bytes"]:
            raise RuntimeError(f"Pinned CUDA 13.0 compiler wheel missing or size-drifted: {wheel}")
        actual = sha256(wheel)
        if actual != expected["sha256"]:
            raise RuntimeError(f"Pinned CUDA 13.0 compiler wheel SHA-256 drift: {wheel} = {actual}")
        with zipfile.ZipFile(wheel) as payload:
            for member in payload.infolist():
                destination = (SITE_PACKAGES / member.filename).resolve()
                if SITE_PACKAGES.resolve() not in destination.parents and destination != SITE_PACKAGES.resolve():
                    raise RuntimeError(f"Unsafe path in CUDA compiler wheel: {member.filename}")
            payload.extractall(SITE_PACKAGES)
        print(f"Overlaid pinned CUDA 13.0 compiler wheel: {filename}", flush=True)


def materialize_cuda_linker_layout() -> None:
    """Expose pip's CUDA runtime files at the conventional toolkit paths."""
    cuda_home = SITE_PACKAGES / "nvidia" / "cu13"
    lib = cuda_home / "lib"
    lib64 = cuda_home / "lib64"
    versioned_cudart = lib / "libcudart.so.13"
    unversioned_cudart = lib / "libcudart.so"
    if not versioned_cudart.is_file():
        raise RuntimeError(f"Pinned CUDA runtime library is missing: {versioned_cudart}")
    if not unversioned_cudart.exists():
        os.symlink(versioned_cudart.name, unversioned_cudart)
    if not lib64.exists():
        os.symlink(lib, lib64, target_is_directory=True)
    if not (lib64 / "libcudart.so").is_file():
        raise RuntimeError(f"CUDA lib64 linker layout is invalid: {lib64}")
    ctypes.CDLL(str(lib64 / "libcudart.so"))
    print(f"Materialized CUDA linker layout: {lib64} -> {lib}", flush=True)


def verify_flashinfer_sm120_toolchain() -> None:
    env = serving_env()
    cuda_home = Path(env["CUDA_HOME"])
    nvcc = cuda_home / "bin" / "nvcc"
    required = [
        nvcc,
        cuda_home / "include" / "cuda_runtime.h",
        cuda_home / "include" / "cccl" / "cub" / "cub.cuh",
        cuda_home / "lib" / "libcudart.so.13",
        cuda_home / "lib64" / "libcudart.so",
        cuda_home / "nvvm" / "bin" / "cicc",
        cuda_home / "nvvm" / "libdevice" / "libdevice.10.bc",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"Exact CUDA 13 wheel toolchain is incomplete: {missing}")
    cicc = cuda_home / "nvvm" / "bin" / "cicc"
    libdevice = cuda_home / "nvvm" / "libdevice" / "libdevice.10.bc"
    if sha256(cicc) != "475a9486f1ccc9408323cc75ea2fa11599f08e9dee137bb7ac7150ce5208c425":
        raise RuntimeError("Pinned CUDA 13.0.88 NVVM cicc binary drift")
    if sha256(libdevice) != "91334d6e12748f6cb5bbf0a1cd965a56bcd93dc4f496d2e5c5f8c6e523094356":
        raise RuntimeError("Pinned CUDA 13.0.88 NVVM libdevice drift")

    probe = subprocess.run(
        [sys.executable, "-c", (
            "import json,torch; "
            "from flashinfer.compilation_context import CompilationContext; "
            "from flashinfer.jit.cpp_ext import get_cuda_path,get_cuda_version; "
            "cap=torch.cuda.get_device_capability(0); "
            "ctx=CompilationContext(); "
            "payload={'capability':cap,'cuda_path':get_cuda_path(),"
            "'cuda_version':str(get_cuda_version()),'targets':sorted(ctx.TARGET_CUDA_ARCHS)}; "
            "print(json.dumps(payload)); "
            "assert cap==(12,0), cap; "
            "assert (12,'0f') in ctx.TARGET_CUDA_ARCHS, ctx.TARGET_CUDA_ARCHS; "
            "assert str(get_cuda_path()).endswith('/nvidia/cu13'), get_cuda_path()"
        )],
        env=env, check=False, capture_output=True, text=True,
    )
    if probe.stdout.strip():
        print("FlashInfer SM120 preflight stdout:", probe.stdout.strip(), flush=True)
    if probe.stderr.strip():
        print("FlashInfer SM120 preflight stderr:", probe.stderr.strip(), flush=True)
    if probe.returncode:
        raise RuntimeError(f"FlashInfer SM120 compiler preflight failed with exit {probe.returncode}")

    version = subprocess.run(
        [str(nvcc), "--version"], env=env, check=True, capture_output=True, text=True
    )
    if "release 13.0," not in version.stdout:
        raise RuntimeError(f"Expected CUDA 13.0 nvcc after pinned overlay, got:\n{version.stdout}")
    print("Exact CUDA compiler:", version.stdout.strip().splitlines()[-1], flush=True)


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


def audit_import_vs_effective_package(imported_model_dir: Path, effective_model_dir: Path) -> None:
    """Measure config and token-ID behavior before serving the exact overlay."""
    probe_source = r'''
import hashlib
import json
import sys
from transformers import AutoConfig, AutoTokenizer


def ids_fingerprint(ids):
    packed = json.dumps(ids, separators=(",", ":")).encode("utf-8")
    return {"count": len(ids), "sha256": hashlib.sha256(packed).hexdigest()}


def inspect(path):
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False)
    config = AutoConfig.from_pretrained(path, local_files_only=True, trust_remote_code=False)
    cases = {
        "arc_grid": "ARC3 observation: [[0,1,2],[2,1,0]]\\nReturn the next tool call as JSON.",
        "unicode_json": '{"game":"ls20","note":"edge → center; café","action":{"x":12,"y":7}}',
        "long_context": ("checkpoint evidence state delta action outcome\\n" * 512),
    }
    encoded = {
        name: ids_fingerprint(tokenizer.encode(text, add_special_tokens=False))
        for name, text in cases.items()
    }
    messages = [
        {"role": "system", "content": "You are an ARC3 game-playing agent."},
        {"role": "user", "content": cases["arc_grid"]},
    ]
    for thinking in (False, True):
        rendered = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=thinking,
            preserve_thinking=True,
        )
        encoded[f"chat_thinking_{str(thinking).lower()}"] = ids_fingerprint(
            tokenizer.encode(rendered, add_special_tokens=False)
        )
    config_dict = config.to_dict()
    config_dict.pop("_name_or_path", None)
    config_dict.pop("name_or_path", None)
    config_payload = json.dumps(config_dict, sort_keys=True, separators=(",", ":"))
    return {
        "tokenizer_class": tokenizer.__class__.__name__,
        "vocab_size": len(tokenizer),
        "special_token_ids": {
            "bos": tokenizer.bos_token_id,
            "eos": tokenizer.eos_token_id,
            "pad": tokenizer.pad_token_id,
        },
        "encoded_cases": encoded,
        "resolved_config_sha256": hashlib.sha256(config_payload.encode("utf-8")).hexdigest(),
    }


imported = inspect(sys.argv[1])
effective = inspect(sys.argv[2])
case_names = sorted(effective["encoded_cases"])
result = {
    "imported": imported,
    "effective": effective,
    "token_ids_equal": all(
        imported["encoded_cases"].get(name) == effective["encoded_cases"][name]
        for name in case_names
    ),
    "resolved_configs_equal": (
        imported["resolved_config_sha256"] == effective["resolved_config_sha256"]
    ),
}
print(json.dumps(result, sort_keys=True))
'''
    probe = subprocess.run(
        [sys.executable, "-c", probe_source, str(imported_model_dir), str(effective_model_dir)],
        env=serving_env(), check=False, capture_output=True, text=True,
    )
    if probe.stderr.strip():
        print("Model package parity probe stderr:", probe.stderr.strip(), flush=True)
    if probe.returncode:
        raise RuntimeError(
            f"Model package parity probe failed with exit {probe.returncode}:\n{probe.stdout}\n{probe.stderr}"
        )
    result = json.loads(probe.stdout)
    result.update({
        "upstream_revision": EXPECTED_MODEL_REVISION,
        "imported_model_dir": str(imported_model_dir),
        "effective_model_dir": str(effective_model_dir),
        "effective_package_byte_exact": True,
    })
    (WORKING_DIR / "nvfp4-package-behavior-audit.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        "Model package behavior audit: "
        f"token_ids_equal={result['token_ids_equal']} "
        f"resolved_configs_equal={result['resolved_configs_equal']}; "
        "serving the byte-exact GCP package",
        flush=True,
    )


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
imported_model_dir, model_dir = resolve_model()
print("Exact wheelhouse:", wheelhouse, flush=True)
print("Exact NVFP4 model:", model_dir, flush=True)
install_exact_arc_runtime()
install_runtime(wheelhouse)
overlay_matching_cuda130_compiler()
materialize_cuda_linker_layout()
verify_flashinfer_sm120_toolchain()
audit_import_vs_effective_package(imported_model_dir, model_dir)
materialized_wheelhouse = WORKING_DIR / "exact-gcp-cu130-wheelhouse"
if wheelhouse == materialized_wheelhouse:
    shutil.rmtree(materialized_wheelhouse, ignore_errors=True)
    print("Removed materialized wheel archive after the exact runtime install", flush=True)
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
