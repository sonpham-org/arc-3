from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
from pathlib import Path


RUNTIME_REF = "sonphamorg/arc3-flashnext-gcp-runtime-exact-v1"
MODEL_CHUNK_DATASET_REF = "sonphamorg/arc3-flashnext-nvfp4-gcp-exact-chunks-v1"
EXPANDED_CHUNK_MANIFEST = "FLASHNEXT_KAGGLE_EXPANDED_FILE_MANIFEST.json"
RUNTIME_ARCHIVE = "flashnext-gcp-container-site-packages.tar.zst"
EXPECTED_RUNTIME_SHA256 = "c06a78d59a74ac278dc2278d26dde6c70c48a4e28bb91fd4fbbefff4484e10f3"
EXPECTED_ZSTD_SHA256 = "7c5468b370f7c47eda07281e3437fafc568f95d10420051e3aa522709f9342c5"
EXPECTED_CONTAINER = (
    "vllm/vllm-openai@sha256:"
    "fc120ece0a388cc0aa1caad4a9f1cd92113484ab7ec2fd0efadd62585be05bf8"
)
MODEL_ID = "RadixArk/Qwen3.8-Flash-Next-NVFP4"
MODEL_REVISION = "7b719225242aacd3dbd3f9407468c2ee9a9d2594"
EXPECTED_UPSTREAM_CHECKPOINT_BYTES = 135_253_622_894
EXPECTED_SAFETENSORS_BYTES = 135_195_303_851
SERVED_MODEL_NAME = MODEL_ID
BASE_URL = "http://127.0.0.1:1234/v1"

WORKING_DIR = Path(os.environ["TAAF_KAGGLE_WORKING_DIR"])
BUNDLE_DIR = Path(os.environ["TAAF_KAGGLE_BUNDLE_DIR"])
RUNTIME_ROOT = WORKING_DIR / "flashnext-gcp-runtime"
SITE_PACKAGES = RUNTIME_ROOT / "dist-packages"
MODEL_DIR = WORKING_DIR / "flashnext-model"
SERVER_LOG = WORKING_DIR / "vllm.log"
SERVER_PID = WORKING_DIR / "vllm.pid"
CURATOR_DIR = WORKING_DIR / "world-model-curator"
CURATOR_LOG = CURATOR_DIR / "curator.log"
CURATOR_PID = CURATOR_DIR / "curator.pid"
ASSEMBLED_SOURCE_DIR = WORKING_DIR / "flashnext-model-source"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(16 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def input_paths() -> dict[str, Path]:
    raw = json.loads(os.environ.get("TAAF_KAGGLE_INPUT_PATHS", "{}"))
    return {str(key): Path(str(value)) for key, value in raw.items()}


def tail(path: Path, lines: int = 120) -> str:
    if not path.is_file():
        return ""
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


def resolve_runtime_archive() -> Path:
    mapped = input_paths().get(RUNTIME_REF)
    candidates = [
        mapped,
        Path("/kaggle/input/arc3-flashnext-gcp-runtime-exact-v1"),
        Path("/kaggle/input/datasets/sonphamorg/arc3-flashnext-gcp-runtime-exact-v1"),
    ]
    for root in candidates:
        archive = root / RUNTIME_ARCHIVE if root else None
        if archive and archive.is_file():
            return archive
    raise FileNotFoundError(f"Exact Flash-Next runtime archive is not mounted: {candidates}")


def install_exact_runtime() -> None:
    archive = resolve_runtime_archive()
    actual = sha256(archive)
    if actual != EXPECTED_RUNTIME_SHA256:
        raise RuntimeError(f"Runtime archive drift: {actual} != {EXPECTED_RUNTIME_SHA256}")
    shutil.rmtree(RUNTIME_ROOT, ignore_errors=True)
    RUNTIME_ROOT.mkdir(parents=True)
    # Kaggle's current image ships GNU tar and the zstd shared libraries, but
    # not the zstd CLI that `tar --zstd` shells out to.  Bundle and verify the
    # tiny decompressor so extraction remains offline and byte-reproducible.
    bundled_zstd = BUNDLE_DIR / "zstd"
    if not bundled_zstd.is_file():
        raise FileNotFoundError(f"Bundled zstd helper is missing: {bundled_zstd}")
    actual_zstd = sha256(bundled_zstd)
    if actual_zstd != EXPECTED_ZSTD_SHA256:
        raise RuntimeError(
            f"Bundled zstd helper drift: {actual_zstd} != {EXPECTED_ZSTD_SHA256}"
        )
    tool_dir = WORKING_DIR / ".packaging-tools"
    tool_dir.mkdir(parents=True, exist_ok=True)
    zstd_tool = tool_dir / "zstd"
    shutil.copy2(bundled_zstd, zstd_tool)
    zstd_tool.chmod(0o755)
    subprocess.run(
        [
            "tar",
            f"--use-compress-program={zstd_tool}",
            "-xf",
            str(archive),
            "-C",
            str(RUNTIME_ROOT),
        ],
        check=True,
    )
    if not (SITE_PACKAGES / "vllm").is_dir():
        raise RuntimeError(f"Extracted runtime is incomplete: {SITE_PACKAGES}")
    check = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import platform,torch,transformers,vllm; "
                "print(platform.python_version(),vllm.__version__,torch.__version__,"
                "transformers.__version__,torch.version.cuda)"
            ),
        ],
        env=serving_env(),
        check=False,
        capture_output=True,
        text=True,
    )
    print("Exact runtime import:", check.stdout.strip(), flush=True)
    if check.returncode:
        raise RuntimeError(f"Exact runtime import failed:\n{check.stderr}")
    expected = "0.1.dev20073+g8e685d198 2.13.0+cu130 5.15.1 13.0"
    if expected not in check.stdout:
        raise RuntimeError(f"Exact serving versions drifted: {check.stdout.strip()}")
    (WORKING_DIR / "serving-environment.txt").write_text(
        check.stdout.strip() + "\n", encoding="utf-8"
    )
    install_runtime_overlays()
    import importlib.util
    research_config = json.loads((BUNDLE_DIR / "PLE_RESEARCH.json").read_text())
    for name, expected in (("ple_loader_research.py", research_config["module_sha256"]), ("install_research.py", research_config["installer_sha256"])):
        if sha256(BUNDLE_DIR / name) != expected:
            raise RuntimeError("Research source hash mismatch: " + name)
    spec = importlib.util.spec_from_file_location("ple_research_installer", BUNDLE_DIR / "install_research.py")
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    installer.install(SITE_PACKAGES, BUNDLE_DIR, WORKING_DIR)


def install_runtime_overlays() -> None:
    records = {
        "qsa.py": (
            SITE_PACKAGES / "vllm/models/qwen3_8_flash_next/nvidia/qsa.py",
            "748addc85efaa8f7df940d1245bc900192f92e1f17af8fa774625758600751cb",
            "cb20493e868b2c1d07023617cb238e51ddcacad8bf1ed676fbd6e8afda9ae0e8",
        ),
        "qsa_ops.py": (
            SITE_PACKAGES / "vllm/models/qwen3_8_flash_next/nvidia/ops/qsa.py",
            "c4ffe3674cafa0ce2dabc39a39f0ddbb4b594bc358ad210ffce9d04383350c7f",
            "877ff779fd127c750c7d773e07181e90841756119e4e27e3c27358448d08eb18",
        ),
        "single_type_kv_cache_manager.py": (
            SITE_PACKAGES / "vllm/v1/core/single_type_kv_cache_manager.py",
            "9ec6cbc0c78f30986f294439f02f57a9586ffbf2939d8f5c4fb968a642625ca2",
            "afb6a793537f64efbaecf3ecd8e2b1ca13dcddac9c0e8f4ec3939f24c28811a0",
        ),
        "scheduler.py": (
            SITE_PACKAGES / "vllm/v1/core/sched/scheduler.py",
            "c710f49e41e974e5b7b8f1cd2f5fb9722523f4da0165252e16351199ebd03124",
            "fd2d9a32b1d06192a18d101403c0d4c6c138dd62385d398c04322e9c26fd54c4",
        ),
    }
    provenance = {}
    for name, (target, expected_base, expected_overlay) in records.items():
        source = BUNDLE_DIR / "runtime_overlays" / name
        observed_base = sha256(target)
        observed_overlay = sha256(source)
        if observed_base != expected_base:
            raise RuntimeError(f"Runtime base drift for {target}: {observed_base}")
        if observed_overlay != expected_overlay:
            raise RuntimeError(f"Runtime overlay drift for {source}: {observed_overlay}")
        shutil.copy2(source, target)
        if sha256(target) != expected_overlay:
            raise RuntimeError(f"Runtime overlay copy failed for {target}")
        provenance[str(target.relative_to(SITE_PACKAGES))] = expected_overlay
    (WORKING_DIR / "runtime-overlays.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def serving_env() -> dict[str, str]:
    env = os.environ.copy()
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(SITE_PACKAGES)
        if not current_pythonpath
        else f"{SITE_PACKAGES}{os.pathsep}{current_pythonpath}"
    )
    packaged_library_dirs = sorted(
        str(path) for path in (SITE_PACKAGES / "nvidia").glob("*/lib") if path.is_dir()
    )
    system_library_dirs = [
        "/usr/local/nvidia/lib64",
        "/usr/local/cuda/lib64",
        "/usr/local/nvidia/lib",
    ]
    current_ld = [entry for entry in env.get("LD_LIBRARY_PATH", "").split(os.pathsep) if entry]
    env["LD_LIBRARY_PATH"] = os.pathsep.join(
        dict.fromkeys(packaged_library_dirs + system_library_dirs + current_ld)
    )
    current_path = [entry for entry in env.get("PATH", "").split(os.pathsep) if entry]
    env["PATH"] = os.pathsep.join(
        dict.fromkeys(["/usr/local/nvidia/bin", "/usr/local/cuda/bin"] + current_path)
    )
    env.update(
        {
            "USE_TF": "0",
            "TRANSFORMERS_NO_TF": "1",
            "TRANSFORMERS_NO_TORCHVISION": "1",
            "VLLM_NO_USAGE_STATS": "1",
            "VLLM_ENABLE_CUDA_COMPATIBILITY": "0",
            "VLLM_PLE_CPU_OFFLOAD": "1",
            "ARC3_PLE_RESEARCH_CONFIG": str(BUNDLE_DIR / "PLE_RESEARCH.json"),
            "ARC3_PLE_RESEARCH_OUTPUT": str(WORKING_DIR / "ple-research"),
            "VLLM_PLE_OFFLOAD_READY_TIMEOUT": "2700",
            "TORCH_CUDA_ARCH_LIST": "12.0f",
            "PYTORCH_ALLOC_CONF": "expandable_segments:True",
            "HF_HUB_OFFLINE": "1",
        }
    )
    return env


def _verify_chunk_file(path: Path, record: dict[str, object]) -> None:
    expected_bytes = int(record["bytes"])
    if not path.is_file() or path.stat().st_size != expected_bytes:
        raise RuntimeError(
            f"Chunk file size drift: {path} = "
            f"{path.stat().st_size if path.exists() else 'missing'} != {expected_bytes}"
        )
    actual_sha256 = sha256(path)
    if actual_sha256 != str(record["sha256"]):
        raise RuntimeError(
            f"Chunk file hash drift: {path} = {actual_sha256} != {record['sha256']}"
        )


def _extract_flat_tar(archive_path: Path, destination: Path) -> None:
    with tarfile.open(archive_path, mode="r:") as archive:
        members = archive.getmembers()
        for member in members:
            if not member.isfile() or Path(member.name).name != member.name:
                raise RuntimeError(
                    f"Unsafe or non-flat member in {archive_path.name}: {member.name}"
                )
            if (destination / member.name).exists():
                raise RuntimeError(
                    f"Duplicate model member while extracting {archive_path.name}: {member.name}"
                )
        archive.extractall(destination, members=members, filter="data")


def _load_expanded_chunk_manifest() -> dict[str, dict[str, object]]:
    path = BUNDLE_DIR / EXPANDED_CHUNK_MANIFEST
    if not path.is_file():
        raise FileNotFoundError(f"Expanded Flash-Next chunk manifest is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("format") != "arc3-flashnext-kaggle-expanded-files-v1":
        raise RuntimeError(
            f"Unexpected expanded Flash-Next manifest format: {payload.get('format')}"
        )
    archives = payload.get("archives")
    if not isinstance(archives, list):
        raise RuntimeError("Expanded Flash-Next manifest has no archive list")
    by_name = {str(record["name"]): record for record in archives}
    if len(by_name) != len(archives):
        raise RuntimeError("Expanded Flash-Next manifest contains duplicate archive names")
    return by_name


def _verify_expanded_chunk_directory(
    directory: Path,
    archive_record: dict[str, object],
    expanded_record: dict[str, object],
) -> None:
    archive_name = str(archive_record["name"])
    if str(expanded_record.get("name")) != archive_name:
        raise RuntimeError(f"Expanded chunk name drift for {archive_name}")
    if int(expanded_record.get("archive_bytes", -1)) != int(archive_record["bytes"]):
        raise RuntimeError(f"Expanded chunk archive size provenance drift for {archive_name}")
    if str(expanded_record.get("archive_sha256")) != str(archive_record["sha256"]):
        raise RuntimeError(f"Expanded chunk archive hash provenance drift for {archive_name}")

    member_records = expanded_record.get("members")
    if not isinstance(member_records, list):
        raise RuntimeError(f"Expanded chunk member manifest missing for {archive_name}")
    expected = {str(record["name"]): record for record in member_records}
    if len(expected) != len(member_records):
        raise RuntimeError(f"Expanded chunk member names are duplicated for {archive_name}")
    actual = {path.name: path for path in directory.iterdir() if path.is_file()}
    nested = [path for path in directory.rglob("*") if path.is_file() and path.parent != directory]
    if nested or set(actual) != set(expected):
        raise RuntimeError(
            f"Expanded chunk contents drift for {archive_name}: "
            f"actual={sorted(actual)} expected={sorted(expected)} nested={nested}"
        )

    def verify_member(item: tuple[str, dict[str, object]]) -> None:
        name, record = item
        path = actual[name]
        expected_bytes = int(record["bytes"])
        if path.stat().st_size != expected_bytes:
            raise RuntimeError(
                f"Expanded chunk member size drift: {path} = "
                f"{path.stat().st_size} != {expected_bytes}"
            )
        actual_sha256 = sha256(path)
        if actual_sha256 != str(record["sha256"]):
            raise RuntimeError(
                f"Expanded chunk member hash drift: {path} = "
                f"{actual_sha256} != {record['sha256']}"
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(verify_member, item) for item in expected.items()]
        for future in concurrent.futures.as_completed(futures):
            future.result()


def _materialize_archive_or_directory(source: Path, destination: Path) -> None:
    if source.is_file():
        _extract_flat_tar(source, destination)
        return
    if not source.is_dir():
        raise RuntimeError(f"Flash-Next packaging source is neither file nor directory: {source}")
    for member in sorted(source.iterdir()):
        if not member.is_file() or (destination / member.name).exists():
            raise RuntimeError(
                f"Unsafe or duplicate expanded model member in {source}: {member.name}"
            )
        (destination / member.name).symlink_to(member)


def materialize_chunked_source() -> Path:
    mapped = input_paths().get(MODEL_CHUNK_DATASET_REF)
    roots = [
        mapped,
        Path("/kaggle/input/arc3-flashnext-nvfp4-gcp-exact-chunks-v1"),
        Path(
            "/kaggle/input/datasets/sonphamorg/"
            "arc3-flashnext-nvfp4-gcp-exact-chunks-v1"
        ),
        Path("/kaggle/input"),
    ]
    manifests: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if not root or not root.exists():
            continue
        candidates = [root / "chunk-manifest.json"]
        if root == Path("/kaggle/input"):
            candidates = list(root.rglob("chunk-manifest.json"))
        for candidate in candidates:
            if candidate.is_file() and candidate.resolve() not in seen:
                seen.add(candidate.resolve())
                manifests.append(candidate.resolve())
    if len(manifests) != 1:
        raise RuntimeError(
            f"Expected exactly one attached Flash-Next chunk manifest, got {manifests}"
        )

    manifest_path = manifests[0]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != "arc3-flashnext-kaggle-model-chunks-v2":
        raise RuntimeError(f"Unexpected Flash-Next chunk format: {manifest.get('format')}")
    if int(manifest.get("source_safetensors_bytes", -1)) != EXPECTED_SAFETENSORS_BYTES:
        raise RuntimeError("Flash-Next chunk manifest safetensors byte count drifted")

    records = list(manifest["base_shards"])
    records.append(manifest["metadata_archive"])
    records.extend(manifest["expert_archives"])
    record_paths: dict[str, Path] = {}
    expanded_manifest = _load_expanded_chunk_manifest()
    input_root = Path("/kaggle/input")
    for record in records:
        name = str(record["name"])
        direct = manifest_path.parent / name
        candidates = [direct] if direct.is_file() else []
        if not candidates:
            candidates = list(input_root.rglob(name))
        if not candidates and name.endswith(".tar"):
            expanded_name = Path(name).stem
            candidates = [
                candidate
                for candidate in input_root.rglob(expanded_name)
                if candidate.is_dir()
            ]
        unique = sorted({candidate.resolve() for candidate in candidates})
        if len(unique) != 1:
            raise RuntimeError(
                f"Expected one attached Flash-Next chunk named {name}, got {unique}"
            )
        record_paths[name] = unique[0]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for record in records:
            name = str(record["name"])
            source = record_paths[name]
            if source.is_file():
                futures.append(executor.submit(_verify_chunk_file, source, record))
            else:
                expanded_record = expanded_manifest.get(name)
                if expanded_record is None:
                    raise RuntimeError(f"No expanded member provenance for {name}")
                futures.append(
                    executor.submit(
                        _verify_expanded_chunk_directory,
                        source,
                        record,
                        expanded_record,
                    )
                )
        for future in concurrent.futures.as_completed(futures):
            future.result()

    shutil.rmtree(ASSEMBLED_SOURCE_DIR, ignore_errors=True)
    ASSEMBLED_SOURCE_DIR.mkdir(parents=True)
    for record in manifest["base_shards"]:
        source = record_paths[str(record["name"])]
        (ASSEMBLED_SOURCE_DIR / source.name).symlink_to(source)
    _materialize_archive_or_directory(
        record_paths[str(manifest["metadata_archive"]["name"])],
        ASSEMBLED_SOURCE_DIR,
    )
    for record in manifest["expert_archives"]:
        _materialize_archive_or_directory(
            record_paths[str(record["name"])],
            ASSEMBLED_SOURCE_DIR,
        )

    safetensors_bytes = sum(
        path.stat().st_size for path in ASSEMBLED_SOURCE_DIR.glob("*.safetensors")
    )
    if safetensors_bytes != EXPECTED_SAFETENSORS_BYTES:
        raise RuntimeError(
            f"Reassembled Flash-Next safetensors drift: {safetensors_bytes} != "
            f"{EXPECTED_SAFETENSORS_BYTES}"
        )
    if not (ASSEMBLED_SOURCE_DIR / "model.safetensors.index.json").is_file():
        raise RuntimeError("Reassembled Flash-Next model index is missing")
    (ASSEMBLED_SOURCE_DIR / "chunk-source-provenance.json").write_text(
        json.dumps(
            {
                "packaging_sources": sorted(
                    {
                        str(path if path.is_dir() else path.parent)
                        for path in record_paths.values()
                    }
                ),
                "model_id": MODEL_ID,
                "revision": MODEL_REVISION,
                "manifest_sha256": sha256(manifest_path),
                "safetensors_bytes": safetensors_bytes,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return ASSEMBLED_SOURCE_DIR


def resolve_source_model() -> Path:
    roots = [
        Path("/kaggle/input/qwen3-8-flash-next-nvfp4-gcp-exact"),
        Path("/kaggle/input/models/sonphamorg/qwen3-8-flash-next-nvfp4-gcp-exact"),
        Path("/kaggle/input"),
    ]
    valid: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for index_path in root.rglob("model.safetensors.index.json"):
            candidate = index_path.parent.resolve()
            if candidate in seen:
                continue
            seen.add(candidate)
            config_path = candidate / "config.json"
            if not config_path.is_file():
                continue
            config = json.loads(config_path.read_text(encoding="utf-8"))
            identity = json.dumps(
                {
                    "architectures": config.get("architectures"),
                    "model_type": config.get("model_type"),
                    "quantization_config": config.get("quantization_config"),
                },
                sort_keys=True,
            ).lower()
            if "flash" in identity and "nvfp4" in identity:
                valid.append(candidate)
    if len(valid) > 1:
        raise RuntimeError(f"Expected one attached Flash-Next NVFP4 model, got {valid}")
    source = valid[0] if valid else materialize_chunked_source()
    safetensors_bytes = sum(path.stat().st_size for path in source.glob("*.safetensors"))
    if safetensors_bytes != EXPECTED_SAFETENSORS_BYTES:
        raise RuntimeError(
            f"Flash-Next safetensors byte count drift: {safetensors_bytes} != "
            f"{EXPECTED_SAFETENSORS_BYTES}"
        )
    return source


def materialize_and_convert_model(source: Path) -> None:
    shutil.rmtree(MODEL_DIR, ignore_errors=True)
    MODEL_DIR.mkdir(parents=True)
    for child in source.iterdir():
        if child.name in {".cache", "model-instance-metadata.json"}:
            continue
        target = MODEL_DIR / child.name
        if child.name == "model.safetensors.index.json":
            shutil.copy2(child, target)
        else:
            target.symlink_to(child, target_is_directory=child.is_dir())
    (MODEL_DIR / "download-info.json").write_text(
        json.dumps(
            {
                "model_id": MODEL_ID,
                "revision": MODEL_REVISION,
                "upstream_checkpoint_bytes": EXPECTED_UPSTREAM_CHECKPOINT_BYTES,
                "safetensors_bytes": EXPECTED_SAFETENSORS_BYTES,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    conversion_log = WORKING_DIR / "ple-conversion.log"
    with conversion_log.open("w", encoding="utf-8") as log:
        subprocess.run(
            [
                sys.executable,
                str(BUNDLE_DIR / "convert_radix_ple.py"),
                str(MODEL_DIR),
                "--delete-fp8",
            ],
            env=serving_env(),
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            check=True,
        )
    expected = json.loads((BUNDLE_DIR / "FLASHNEXT_GCP_MODEL_INFO.json").read_text())[
        "ple_conversion"
    ]
    observed = json.loads((MODEL_DIR / "ple-bf16-conversion.json").read_text())
    expected_files = {
        item["target"]: (int(item["target_bytes"]), item["target_sha256"])
        for item in expected["files"]
    }
    observed_files = {
        item["target"]: (int(item["target_bytes"]), item["target_sha256"])
        for item in observed["files"]
    }
    if observed_files != expected_files or observed["index_sha256"] != expected["index_sha256"]:
        raise RuntimeError("Deterministic PLE conversion does not match the GCP winner")
    provenance = {
        "model_id": MODEL_ID,
        "revision": MODEL_REVISION,
        "source_checkpoint_bytes": EXPECTED_UPSTREAM_CHECKPOINT_BYTES,
        "source_safetensors_bytes": EXPECTED_SAFETENSORS_BYTES,
        "conversion": observed,
        "routed_experts": "unchanged private Kaggle model input symlinks",
        "container": EXPECTED_CONTAINER,
    }
    (WORKING_DIR / "flashnext-model-provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )


def request_json(path: str, payload: dict | None = None, timeout: int = 30) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def stop_server() -> None:
    if SERVER_PID.is_file():
        try:
            os.killpg(int(SERVER_PID.read_text().strip()), 15)
        except (OSError, ValueError):
            pass
        SERVER_PID.unlink(missing_ok=True)
        time.sleep(5)


def launch_server(kv_dtype: str) -> subprocess.Popen:
    stop_server()
    SERVER_LOG.write_text("", encoding="utf-8")
    command = [
        sys.executable,
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        str(MODEL_DIR),
        "--served-model-name",
        SERVED_MODEL_NAME,
        "--host",
        "127.0.0.1",
        "--port",
        "1234",
        "--tensor-parallel-size",
        "1",
        "--distributed-executor-backend",
        "mp",
        "--gpu-memory-utilization",
        "0.965",
        "--max-model-len",
        "102985",
        "--max-num-seqs",
        "7",
        "--max-num-batched-tokens",
        "6144",
        "--kv-cache-dtype",
        kv_dtype,
        "--scheduling-policy",
        "fcfs",
        "--watermark",
        "0.000",
        "--enable-chunked-prefill",
        "--enable-prefix-caching",
        "--enable-prompt-tokens-details",
        "--no-enable-flashinfer-autotune",
        "--enable-auto-tool-choice",
        "--tool-call-parser",
        "qwen3_xml",
        "--generation-config",
        "vllm",
        "--default-chat-template-kwargs",
        '{"preserve_thinking": true}',
        "--reasoning-parser",
        "qwen3",
        "--cudagraph-capture-sizes",
        *map(str, [1, 2, 4, 8, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 24, 32, 40]),
    ]
    log = SERVER_LOG.open("w", encoding="utf-8")
    process = subprocess.Popen(
        command,
        env=serving_env(),
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    SERVER_PID.write_text(str(process.pid), encoding="utf-8")
    return process


def wait_server(process: subprocess.Popen, timeout_seconds: int = 2700) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            request_json("/models", timeout=5)
            return True
        except Exception:
            time.sleep(10)
    return False


def run_capacity_smoke(kv_dtype: str) -> None:
    filler = "x " * 9000

    def call(index: int) -> float:
        started = time.monotonic()
        response = request_json(
            "/chat/completions",
            {
                "model": SERVED_MODEL_NAME,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"This is capacity probe {index}. Ignore the filler and return only OK. "
                            + filler
                        ),
                    }
                ],
                "temperature": 0.0,
                "max_tokens": 16,
                "chat_template_kwargs": {
                    "enable_thinking": False,
                    "preserve_thinking": True,
                },
            },
            timeout=900,
        )
        if not response.get("choices"):
            raise RuntimeError(response)
        return time.monotonic() - started

    started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=7) as pool:
        timings = list(pool.map(call, range(7)))
    summary = {
        "model": SERVED_MODEL_NAME,
        "kv_dtype": kv_dtype,
        "max_num_seqs": 7,
        "requests": len(timings),
        "wall_seconds": time.monotonic() - started,
        "min_seconds": min(timings),
        "max_seconds": max(timings),
        "mean_seconds": sum(timings) / len(timings),
    }
    (WORKING_DIR / "model-smoke.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )


def start_exact_server() -> str:
    kv_dtype = "fp8"
    process = launch_server(kv_dtype)
    if not wait_server(process):
        raise RuntimeError(f"Flash-Next FP8-KV server failed:\n{tail(SERVER_LOG)}")
    run_capacity_smoke(kv_dtype)
    (WORKING_DIR / "kv-dtype-used.txt").write_text(kv_dtype + "\n", encoding="utf-8")
    return kv_dtype


def start_curator() -> None:
    print("Curator disabled: clean reminder recipe", flush=True)


def persist_gameplay_environment(kv_dtype: str) -> None:
    setup_env_path = Path(os.environ["TAAF_KAGGLE_SETUP_ENV"])
    persisted = json.loads(setup_env_path.read_text(encoding="utf-8"))
    persisted.update(
        {
            "PYTHONPATH": serving_env()["PYTHONPATH"],
            "LD_LIBRARY_PATH": serving_env().get("LD_LIBRARY_PATH", ""),
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
            "LOCAL_ANALYZER_CONTEXT_WINDOW": "102985",
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
            "ARC3_ANIMATION_CHECKPOINT_ENABLED": "1",
            "ARC3_ANIMATION_CHECKPOINT_MIN_CHANGED": "2",
            "ARC3_ANIMATION_EXPOSED_KEYFRAMES": "12",
            "ARC3_ANIMATION_BASELINE_MIN_SAMPLES": "5",
            "ARC3_ANIMATION_FAMILY_MIN_SAMPLES": "5",
            "ARC3_ANIMATION_HUD_BORDER": "0",
            "ARC3_ANIMATION_MIN_SPATIAL_FRAMES": "4",
            "ARC3_ANIMATION_MIN_SPATIAL_UNIQUE_CELLS": "8",
            "ARC3_ANIMATION_MIN_SPATIAL_CHANGE_SUM": "32",
            "ARC3_ANIMATION_STORYBOARD_MAX_TOKENS": "2000",
            "ARC3_ANIMATION_REGION_MIN_TRANSITION_FRAMES": "2",
            "ARC3_ANIMATION_REGION_MAX_COUNT": "4",
            "ARC3_ANIMATION_REGION_MAX_FRAMES": "12",
            "ARC3_ANIMATION_CHECKPOINT_MAX_PER_LEVEL": "3",
            "ARC3_ANIMATION_CHECKPOINT_COOLDOWN_ACTIONS": "5",
            "ARC3_REEXPLORE_STRICT": "",
            "ARC3_GAME_SUBSET": "",
            "ARC3_STATE_GRAPH": "",
            "ARC3_FRAME_MODE": "full",
            "ARC3_ACTION_CAP": "14",
            "ARC3_POST_LEVEL_UNCAPPED_TURNS": "0",
            "ARC3_EXECUTION_MODE": "0",
            "ARC3_PERSISTENT_GAME_MODEL": "0",
            "ARC3_EXECUTION_CONFIRMATIONS": "2",
            "ARC3_EXECUTION_LEASE_ACTIONS": "3",
            "ARC3_SYMBOLIC_SEARCH": "0",
            "ARC3_PROGRAMMATIC_WORKSPACE": "0",
            "ARC3_HISTORY_MODE": "full_context",
            "ARC3_PERSISTENT_HISTORY_ASSISTANT_TURNS": "30",
            "ARC3_COMMON_THEMES_PATH": "",
            "ARC3_COMMON_THEMES_INJECTION_LOG": "",
            "ARC3_COMMON_THEMES_MAX": "0",
            "ARC3_COMMON_THEMES_MAX_CHARS": "6000",
            "FLASHNEXT_KV_DTYPE_USED": kv_dtype,
            "FLASHNEXT_MAX_NUM_SEQS": "7",
            "FLASHNEXT_MAX_NUM_BATCHED_TOKENS": "6144",
            "FLASHNEXT_CLIENT_CONCURRENCY": "7",
            "FLASHNEXT_MTP_ENABLED": "0",
            "FLASHNEXT_GAMEPLAY_LIMIT_SECONDS": "1938",
        }
    )
    for disabled in (
        "ARC3_REPLAY_ENABLED",
        "ARC3_REPLAY_ARM",
        "ARC3_REPLAY_TRIGGER_REMINDER",
        "ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED",
        "ARC3_SAME_CONTEXT_LEVEL_REFLECTION_VERSION",
        "ARC3_CONTEXT_COMPACTION_ENABLED",
        "ARC3_CONTEXT_COMPACTION_TRIGGER_FRACTION",
        "ARC3_CONTEXT_COMPACTION_KEEP_ASSISTANT_TURNS",
        "ARC3_CONTEXT_COMPACTION_MAX_TOKENS",
        "ARC3_CONTEXT_TRIM_TARGET",
        "ARC3_CONTEXT_TRIM_TARGET_FRACTION",
        "ARC3_CONTEXT_HISTORY_MAX_ASSISTANT_TURNS",
        "ARC3_REASONING_POLICY",
        "ARC3_VISUAL_TOOLKIT_MODE",
    ):
        persisted.pop(disabled, None)
    # One coupled switch per added feature; read before analyzer imports.
    feature_env = json.loads((BUNDLE_DIR / "MTR_FEATURES.json").read_text())
    expected_keys = {"ARC3_VISUAL_TRANSITION_MODE", "ARC3_CPU_TOOLKIT_ENABLED", "ARC3_BUDGET_REMINDER_ENABLED"}
    if set(feature_env) != expected_keys:
        raise RuntimeError("Unexpected MTR feature configuration keys")
    if feature_env["ARC3_VISUAL_TRANSITION_MODE"] not in {"control", "metadata"}:
        raise RuntimeError("This candidate permits control or metadata, not extra images")
    if any(feature_env[k] not in {"0", "1"} for k in expected_keys - {"ARC3_VISUAL_TRANSITION_MODE"}):
        raise RuntimeError("MTR feature flags must be 0 or 1")
    persisted.update(feature_env)
    config = json.loads((BUNDLE_DIR / "CONFIG_FLAGS.json").read_text())
    persisted.update({k: v for k, v in config["recipe"]["extra_environment"].items() if k.startswith("ARC3_PLE_")})
    prompt_flags = json.loads((BUNDLE_DIR / "PROMPT_FLAGS.json").read_text())
    expected_prompt_flags = {'ARC3_PROMPT_ABLATE_REPEAT_STRATEGY': '1', 'ARC3_PROMPT_ABLATE_REPEAT_MOUSE': '0', 'ARC3_PROMPT_ABLATE_VIEW': '0', 'ARC3_PROMPT_ABLATE_LOOP': '0', 'ARC3_PROMPT_ABLATE_SEARCH': '0', 'ARC3_PROMPT_ABLATE_COORDS': '0', 'ARC3_PROMPT_ABLATE_PRIORS': '0', 'ARC3_PROMPT_ABLATE_TRANSITION': '1', 'ARC3_LOOP_VARIANT': 'a', 'ARC3_INPUT_ACCESS': '0'}
    if prompt_flags != expected_prompt_flags:
        raise RuntimeError("Unexpected minimal-only prompt flags")
    persisted.update(prompt_flags)
    setup_env_path.write_text(
        json.dumps(persisted, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


install_exact_runtime()
source_model = resolve_source_model()
print("Exact private Flash-Next model:", source_model, flush=True)
materialize_and_convert_model(source_model)
kv_dtype_used = start_exact_server()
start_curator()
persist_gameplay_environment(kv_dtype_used)
print(
    "Flash-Next GCP-exact setup ready: 7 clients, 7 admitted sequences, "
    f"6144 batched tokens, KV={kv_dtype_used}, 1,938-second nominal competition gameplay cap",
    flush=True,
)
