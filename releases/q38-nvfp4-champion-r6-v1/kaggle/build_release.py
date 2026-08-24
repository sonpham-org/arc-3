from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "CHAMPION_LOCK.json").read_text(encoding="utf-8"))
DATASET_ID = "sonphamorg/arc3-q38-champion-hermetic-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def copytree_exact(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(source)
    shutil.copytree(source, destination)


def verify_model_assets(path: Path) -> None:
    for name, expected in LOCK["model"]["artifacts"].items():
        if name in {"model.safetensors", "model_mtp.safetensors"}:
            continue
        artifact = path / name
        if not artifact.is_file() or sha256(artifact) != expected:
            raise RuntimeError(f"Exact GCP model asset missing or drifted: {artifact}")


def build_dataset(vendor: Path, output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    output.mkdir(parents=True)
    bundle = ROOT / "artifacts" / "bundle-q38-ce-think-nvfp4-crossgame-singlecopy-20260820.tgz"
    if sha256(bundle) != LOCK["objects"][1]["sha256"]:
        raise RuntimeError("Champion source/deployment bundle drift")
    with tarfile.open(bundle, "r:gz") as archive:
        archive.extractall(output, filter="data")

    setup = ROOT / "kaggle" / "kaggle_nvfp4_world_model_setup.py"
    shutil.copy2(setup, output / setup.name)
    shutil.copy2(ROOT / "artifacts" / "nvfp4_cross_game_curator.py", output / "nvfp4_cross_game_curator.py")
    copytree_exact(ROOT / "artifacts" / "engine-wheels", output / "engine-wheels")

    compiler_source = vendor / "cuda130-sm120-compiler"
    model_assets_source = vendor / "exact-gcp-model-assets"
    copytree_exact(compiler_source, output / compiler_source.name)
    verify_model_assets(model_assets_source)
    copytree_exact(model_assets_source, output / model_assets_source.name)

    write_json(
        output / "setup_commands.json",
        ['"$PYTHON" "$TAAF_KAGGLE_BUNDLE_DIR/kaggle_nvfp4_world_model_setup.py"'],
    )
    write_json(output / "teardown_commands.json", [])
    write_json(
        output / "dataset-metadata.json",
        {
            "title": "ARC3 Q38 champion hermetic v1",
            "id": DATASET_ID,
            "licenses": [{"name": "MIT"}],
        },
    )
    write_json(
        output / "CHAMPION_LOCK.json",
        LOCK,
    )

    files = []
    for path in sorted(p for p in output.rglob("*") if p.is_file()):
        if path.name == "RELEASE_FILES.json":
            continue
        files.append(
            {
                "path": path.relative_to(output).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    write_json(
        output / "RELEASE_FILES.json",
        {
            "release_id": LOCK["release_id"],
            "dataset_id": DATASET_ID,
            "files": files,
        },
    )
    print(json.dumps({"dataset": str(output), "files": len(files), "dataset_id": DATASET_ID}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--vendor",
        type=Path,
        required=True,
        help="Verified prior dataset directory containing exact-gcp-model-assets/ and cuda130-sm120-compiler/",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build_dataset(args.vendor.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
