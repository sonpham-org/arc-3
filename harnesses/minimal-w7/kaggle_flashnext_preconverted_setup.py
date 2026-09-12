"""Launch the exact Flash-Next candidate from an immutable preconverted model.

This is a packaging-only wrapper around ``kaggle_flashnext_setup.py``.  It
reuses the exact runtime, vLLM command, curator, and solver environment while
replacing only chunk reconstruction and PLE conversion with verification of a
pinned, already-converted Kaggle model variation.
"""

from __future__ import annotations

from pathlib import Path


bundle_dir = Path(__file__).resolve().parent
base_path = bundle_dir / "kaggle_flashnext_setup.py"
base = base_path.read_text(encoding="utf-8")

start = base.index("def resolve_source_model() -> Path:\n")
end = base.index("\ndef request_json(", start)

replacement = r'''def resolve_source_model() -> Path:
    markers = sorted(
        path.resolve()
        for path in Path("/kaggle/input").rglob(
            "PRECONVERTED_MODEL_PROVENANCE.json"
        )
        if path.is_file()
    )
    if len(markers) != 1:
        raise RuntimeError(
            "Expected exactly one immutable preconverted Flash-Next model, "
            f"got {markers}"
        )

    provenance_path = markers[0]
    source = provenance_path.parent
    # Kaggle may mount the permanent variation as three expanded TAR shards to
    # stay below the model-registry file-count ceiling.  Build a tiny symlink
    # view in /kaggle/working; this copies no checkpoint bytes and keeps startup
    # warm-on-disk.
    if not (source / "model.safetensors.index.json").is_file():
        shard_dirs = sorted(
            path
            for path in source.parent.iterdir()
            if path.is_dir() and path.name.startswith("serving-part-")
        )
        if len(shard_dirs) != 3:
            raise RuntimeError(
                "Expected three expanded immutable serving shards, "
                f"got {shard_dirs}"
            )
        linked = WORKING_DIR / "flashnext-preconverted-model"
        linked.mkdir(parents=True, exist_ok=True)
        observed_names = set()
        for shard in shard_dirs:
            for mounted in sorted(shard.iterdir()):
                if not mounted.is_file():
                    raise RuntimeError(
                        f"Unexpected nested entry in serving shard: {mounted}"
                    )
                if mounted.name in observed_names:
                    raise RuntimeError(
                        f"Duplicate file across serving shards: {mounted.name}"
                    )
                observed_names.add(mounted.name)
                (linked / mounted.name).symlink_to(mounted)
        source = linked
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if provenance.get("format") != (
        "arc3-flashnext-preconverted-serving-model-provenance-v1"
    ):
        raise RuntimeError("Unexpected preconverted model provenance format")
    if provenance.get("model_id") != MODEL_ID:
        raise RuntimeError("Preconverted model id drifted")
    if provenance.get("revision") != MODEL_REVISION:
        raise RuntimeError("Preconverted model revision drifted")
    if int(provenance.get("source_safetensors_bytes", -1)) != (
        EXPECTED_SAFETENSORS_BYTES
    ):
        raise RuntimeError("Preconverted source byte provenance drifted")

    manifest_path = source / "PRECONVERTED_MODEL_FILE_MANIFEST.json"
    if sha256(manifest_path) != provenance.get("file_manifest_sha256"):
        raise RuntimeError("Preconverted file-manifest hash drifted")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("model_id") != MODEL_ID or manifest.get("revision") != MODEL_REVISION:
        raise RuntimeError("Preconverted file manifest identity drifted")
    files = list(manifest.get("files", []))
    if len(files) != int(provenance.get("file_count", -1)):
        raise RuntimeError("Preconverted file count drifted")
    if sum(int(item["bytes"]) for item in files) != int(
        provenance.get("total_bytes", -1)
    ):
        raise RuntimeError("Preconverted manifest total bytes drifted")
    # The original offline audit also recorded Hugging Face's download cache
    # receipts.  Kaggle's direct-file model uploader intentionally skips the
    # nested ``.cache`` directory; those receipts are neither model payload nor
    # runtime dependencies.  Pin their exact audited shape, then verify every
    # serving-payload record that Kaggle does mount.
    cache_receipts = [
        item for item in files if str(item["path"]).startswith(".cache/")
    ]
    if len(cache_receipts) != 840 or sum(
        int(item["bytes"]) for item in cache_receipts
    ) != 47_407:
        raise RuntimeError("Preconverted cache-receipt provenance drifted")
    reserved_dataset_metadata = [
        item for item in files if str(item["path"]) == "dataset-metadata.json"
    ]
    if len(reserved_dataset_metadata) != 1 or int(
        reserved_dataset_metadata[0]["bytes"]
    ) != 418:
        raise RuntimeError("Preconverted dataset-metadata provenance drifted")
    serving_files = [
        item
        for item in files
        if not str(item["path"]).startswith(".cache/")
        and str(item["path"]) != "dataset-metadata.json"
    ]
    for item in serving_files:
        path = source / str(item["path"])
        if not path.is_file() or path.stat().st_size != int(item["bytes"]):
            raise RuntimeError(f"Preconverted mounted file drifted: {path}")

    expected = json.loads(
        (BUNDLE_DIR / "FLASHNEXT_GCP_MODEL_INFO.json").read_text()
    )["ple_conversion"]
    observed = json.loads((source / "ple-bf16-conversion.json").read_text())
    expected_files = {
        item["target"]: (int(item["target_bytes"]), item["target_sha256"])
        for item in expected["files"]
    }
    observed_files = {
        item["target"]: (int(item["target_bytes"]), item["target_sha256"])
        for item in observed["files"]
    }
    if observed_files != expected_files:
        raise RuntimeError("Preconverted PLE file hashes differ from the GCP winner")
    if observed.get("index_sha256") != expected.get("index_sha256"):
        raise RuntimeError("Preconverted PLE index provenance differs from the GCP winner")
    if sha256(source / "model.safetensors.index.json") != expected["index_sha256"]:
        raise RuntimeError("Mounted preconverted index hash drifted")
    if list(source.glob("model-plefp8-*.safetensors")):
        raise RuntimeError("Mounted serving model still contains FP8 PLE source files")
    for name, (expected_bytes, _) in expected_files.items():
        target = source / name
        if not target.is_file() or target.stat().st_size != expected_bytes:
            raise RuntimeError(f"Mounted preconverted PLE file drifted: {target}")

    print(
        "Exact immutable preconverted Flash-Next model verified: "
        f"{source} ({len(serving_files)} serving files, "
        f"{sum(int(item['bytes']) for item in serving_files)} bytes)",
        flush=True,
    )
    return source


def materialize_and_convert_model(source: Path) -> None:
    global MODEL_DIR
    MODEL_DIR = source.resolve()
    observed = json.loads((MODEL_DIR / "ple-bf16-conversion.json").read_text())
    provenance = {
        "model_id": MODEL_ID,
        "revision": MODEL_REVISION,
        "source_checkpoint_bytes": EXPECTED_UPSTREAM_CHECKPOINT_BYTES,
        "source_safetensors_bytes": EXPECTED_SAFETENSORS_BYTES,
        "conversion": observed,
        "serving_model": str(MODEL_DIR),
        "preconverted_immutable_input": True,
        "routed_experts": "unchanged immutable Kaggle model files",
        "container": EXPECTED_CONTAINER,
    }
    (WORKING_DIR / "flashnext-model-provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
'''

patched = base[:start] + replacement + base[end:]
if patched == base or "materialize_chunked_source()" in patched[start:end]:
    raise RuntimeError("Preconverted setup wrapper did not replace the cold path")

globals()["__file__"] = str(base_path)
exec(compile(patched, str(base_path), "exec"), globals(), globals())
